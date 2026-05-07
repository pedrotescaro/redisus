export interface ImageQualityResult {
  status: 'good' | 'regular' | 'poor';
  score: number;
  issues: string[];
  metrics: {
    width: number;
    height: number;
    brightness: number;
    contrast: number;
    sharpness: number;
  };
  preprocessing: string[];
}

export interface PreparedAnalyzerImage {
  file: File;
  previewUrl: string;
  quality: ImageQualityResult;
}

const PREPROCESSING_STEPS = ['median_low_pass', 'gaussian_low_pass', 'histogram_equalization'];

async function loadImage(source: File | string) {
  const objectUrl = typeof source === 'string' ? source : URL.createObjectURL(source);
  const image = new Image();
  image.crossOrigin = 'anonymous';

  try {
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error('Nao foi possivel carregar a imagem.'));
      image.src = objectUrl;
    });
  } finally {
    if (typeof source !== 'string') URL.revokeObjectURL(objectUrl);
  }

  return image;
}

function clampByte(value: number) {
  return Math.max(0, Math.min(255, Math.round(value)));
}

function median(values: number[]) {
  const sorted = values.slice().sort((left, right) => left - right);
  return sorted[Math.floor(sorted.length / 2)];
}

function medianFilter(imageData: ImageData) {
  const { width, height, data } = imageData;
  const output = new Uint8ClampedArray(data);

  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const reds: number[] = [];
      const greens: number[] = [];
      const blues: number[] = [];

      for (let yy = -1; yy <= 1; yy += 1) {
        for (let xx = -1; xx <= 1; xx += 1) {
          const offset = ((y + yy) * width + x + xx) * 4;
          reds.push(data[offset]);
          greens.push(data[offset + 1]);
          blues.push(data[offset + 2]);
        }
      }

      const target = (y * width + x) * 4;
      output[target] = median(reds);
      output[target + 1] = median(greens);
      output[target + 2] = median(blues);
    }
  }

  return new ImageData(output, width, height);
}

function gaussianFilter(imageData: ImageData) {
  const { width, height, data } = imageData;
  const output = new Uint8ClampedArray(data);
  const kernel = [
    [1, 2, 1],
    [2, 4, 2],
    [1, 2, 1]
  ];

  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const sum = [0, 0, 0];
      for (let yy = -1; yy <= 1; yy += 1) {
        for (let xx = -1; xx <= 1; xx += 1) {
          const weight = kernel[yy + 1][xx + 1];
          const offset = ((y + yy) * width + x + xx) * 4;
          sum[0] += data[offset] * weight;
          sum[1] += data[offset + 1] * weight;
          sum[2] += data[offset + 2] * weight;
        }
      }
      const target = (y * width + x) * 4;
      output[target] = clampByte(sum[0] / 16);
      output[target + 1] = clampByte(sum[1] / 16);
      output[target + 2] = clampByte(sum[2] / 16);
    }
  }

  return new ImageData(output, width, height);
}

function equalizeHistogram(imageData: ImageData) {
  const { width, height, data } = imageData;
  const histogram = new Array<number>(256).fill(0);

  for (let index = 0; index < data.length; index += 4) {
    const luminance = Math.round(0.299 * data[index] + 0.587 * data[index + 1] + 0.114 * data[index + 2]);
    histogram[luminance] += 1;
  }

  const cdf = new Array<number>(256).fill(0);
  histogram.reduce((sum, value, index) => {
    cdf[index] = sum + value;
    return cdf[index];
  }, 0);

  const total = width * height;
  const cdfMin = cdf.find(value => value > 0) || 0;
  const output = new Uint8ClampedArray(data);

  for (let index = 0; index < data.length; index += 4) {
    const luminance = Math.round(0.299 * data[index] + 0.587 * data[index + 1] + 0.114 * data[index + 2]);
    const equalized = clampByte(((cdf[luminance] - cdfMin) / Math.max(total - cdfMin, 1)) * 255);
    const factor = luminance > 0 ? equalized / luminance : 1;
    output[index] = clampByte(data[index] * factor);
    output[index + 1] = clampByte(data[index + 1] * factor);
    output[index + 2] = clampByte(data[index + 2] * factor);
  }

  return new ImageData(output, width, height);
}

function computeQuality(canvas: HTMLCanvasElement, imageData: ImageData): ImageQualityResult {
  const { width, height, data } = imageData;
  const luminanceValues: number[] = [];
  let gradientSum = 0;

  for (let y = 0; y < height; y += 2) {
    for (let x = 0; x < width; x += 2) {
      const offset = (y * width + x) * 4;
      const luminance = 0.299 * data[offset] + 0.587 * data[offset + 1] + 0.114 * data[offset + 2];
      luminanceValues.push(luminance);

      if (x + 2 < width && y + 2 < height) {
        const rightOffset = (y * width + x + 2) * 4;
        const bottomOffset = ((y + 2) * width + x) * 4;
        const right = 0.299 * data[rightOffset] + 0.587 * data[rightOffset + 1] + 0.114 * data[rightOffset + 2];
        const bottom = 0.299 * data[bottomOffset] + 0.587 * data[bottomOffset + 1] + 0.114 * data[bottomOffset + 2];
        gradientSum += Math.abs(luminance - right) + Math.abs(luminance - bottom);
      }
    }
  }

  const brightness = luminanceValues.reduce((sum, value) => sum + value, 0) / Math.max(luminanceValues.length, 1);
  const variance =
    luminanceValues.reduce((sum, value) => sum + (value - brightness) ** 2, 0) / Math.max(luminanceValues.length, 1);
  const contrast = Math.sqrt(variance);
  const sharpness = gradientSum / Math.max(luminanceValues.length, 1);
  const issues: string[] = [];

  if (width < 480 || height < 360) issues.push('low_resolution');
  if (brightness < 55) issues.push('low_light');
  if (brightness > 220) issues.push('overexposure');
  if (contrast < 24) issues.push('low_contrast');
  if (sharpness < 8) issues.push('possible_blur');

  const score = Math.max(0, Math.min(100, 100 - issues.length * 18 - (sharpness < 12 ? 8 : 0)));
  const status = score >= 78 ? 'good' : score >= 52 ? 'regular' : 'poor';

  return {
    status,
    score,
    issues,
    metrics: {
      width: canvas.width,
      height: canvas.height,
      brightness: Math.round(brightness),
      contrast: Math.round(contrast),
      sharpness: Math.round(sharpness)
    },
    preprocessing: PREPROCESSING_STEPS
  };
}

async function canvasToFile(canvas: HTMLCanvasElement, fileName: string) {
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(result => (result ? resolve(result) : reject(new Error('Nao foi possivel gerar imagem filtrada.'))), 'image/jpeg', 0.92);
  });
  return new File([blob], fileName, { type: 'image/jpeg' });
}

export async function fileFromImageSource(source: File | string, fileName = 'heal-analyzer-image.jpg') {
  if (source instanceof File) return source;

  const response = await fetch(source);
  if (!response.ok) {
    throw new Error('Nao foi possivel carregar a imagem vinculada a avaliacao.');
  }
  const blob = await response.blob();
  return new File([blob], fileName, { type: blob.type || 'image/jpeg' });
}

export async function prepareImageForClinicalAnalysis(source: File | string): Promise<PreparedAnalyzerImage> {
  const image = await loadImage(source);
  const naturalWidth = image.naturalWidth || image.width;
  const naturalHeight = image.naturalHeight || image.height;
  const maxSide = 1400;
  const scale = Math.min(1, maxSide / Math.max(naturalWidth, naturalHeight, 1));
  const width = Math.max(1, Math.round(naturalWidth * scale));
  const height = Math.max(1, Math.round(naturalHeight * scale));
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  if (!context) throw new Error('Canvas indisponivel para processamento de imagem.');

  context.drawImage(image, 0, 0, width, height);
  let imageData = context.getImageData(0, 0, width, height);
  const quality = computeQuality(canvas, imageData);
  imageData = medianFilter(imageData);
  imageData = gaussianFilter(imageData);
  imageData = equalizeHistogram(imageData);
  context.putImageData(imageData, 0, 0);

  const fileName = source instanceof File ? `filtered-${source.name.replace(/\.[^.]+$/, '')}.jpg` : 'filtered-assessment-image.jpg';
  return {
    file: await canvasToFile(canvas, fileName),
    previewUrl: canvas.toDataURL('image/jpeg', 0.9),
    quality,
  };
}
