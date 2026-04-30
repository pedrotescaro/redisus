import type { ImgHTMLAttributes } from 'react';

type NextImageProps = Omit<ImgHTMLAttributes<HTMLImageElement>, 'src'> & {
  src: string | { src?: string };
  priority?: boolean;
};

export default function Image({ src, priority: _priority, alt = '', ...props }: NextImageProps) {
  const resolvedSrc = typeof src === 'string' ? src : src.src ?? '';

  return <img src={resolvedSrc} alt={alt} {...props} />;
}
