"""
REDISUS - Sistema de Diagnóstico de Feridas
Módulo de Captura de Vídeo (Webcam/Câmera Mobile)

Este módulo gerencia a captura de frames em tempo real com otimizações
para baixa latência e threading assíncrono.
"""
import threading
import time
from dataclasses import dataclass
from queue import Queue
from typing import Callable, Optional, Tuple

import cv2
import numpy as np
from loguru import logger

from ..core.config import CameraConfig
from ..core.exceptions import CameraError, CameraInitializationError, CameraNotFoundError


@dataclass
class FrameData:
    """Container para dados do frame capturado"""
    frame: np.ndarray
    timestamp: float
    frame_number: int
    resolution: Tuple[int, int]
    
    @property
    def width(self) -> int:
        return self.resolution[0]
    
    @property
    def height(self) -> int:
        return self.resolution[1]


class VideoStream:
    """
    Classe para captura de vídeo em tempo real com threading.
    
    Características:
    - Captura assíncrona em thread separada
    - Buffer mínimo para reduzir latência
    - Suporte a webcam e câmeras IP
    - Callback para processamento de frames
    
    Uso:
        stream = VideoStream(camera_id=0)
        stream.start()
        
        while True:
            frame_data = stream.read()
            if frame_data is not None:
                cv2.imshow("Frame", frame_data.frame)
        
        stream.stop()
    """
    
    def __init__(
        self,
        camera_id: int = 0,
        config: Optional[CameraConfig] = None,
        frame_callback: Optional[Callable[[FrameData], None]] = None
    ):
        """
        Inicializa o stream de vídeo.
        
        Args:
            camera_id: ID da câmera (0 para webcam padrão)
            config: Configurações da câmera
            frame_callback: Função callback chamada a cada frame capturado
        """
        self.camera_id = camera_id
        self.config = config or CameraConfig()
        self.frame_callback = frame_callback
        
        # Estado interno
        self._capture: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._frame_queue: Queue[FrameData] = Queue(maxsize=self.config.buffer_size)
        self._frame_count = 0
        self._last_frame: Optional[FrameData] = None
        self._lock = threading.Lock()
        
        # Métricas
        self._fps_actual = 0.0
        self._fps_timer = time.time()
        self._fps_counter = 0
        
    def _initialize_camera(self) -> cv2.VideoCapture:
        """Inicializa e configura a câmera"""
        logger.info(f"Inicializando câmera {self.camera_id}...")
        
        # Tenta diferentes backends
        backends = [
            cv2.CAP_DSHOW,   # DirectShow (Windows)
            cv2.CAP_MSMF,    # Media Foundation (Windows)
            cv2.CAP_ANY      # Auto-detect
        ]
        
        capture = None
        for backend in backends:
            capture = cv2.VideoCapture(self.camera_id, backend)
            if capture.isOpened():
                logger.debug(f"Câmera aberta com backend: {backend}")
                break
        
        if capture is None or not capture.isOpened():
            raise CameraNotFoundError(
                f"Não foi possível abrir a câmera {self.camera_id}. "
                "Verifique se a câmera está conectada."
            )
        
        # Configura resolução e FPS
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        capture.set(cv2.CAP_PROP_FPS, self.config.fps)
        
        # Configura buffer mínimo para baixa latência
        capture.set(cv2.CAP_PROP_BUFFERSIZE, self.config.buffer_size)
        
        # Desabilita auto-focus se necessário
        if not self.config.auto_focus:
            capture.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        
        # Verifica resolução obtida
        actual_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = capture.get(cv2.CAP_PROP_FPS)
        
        logger.info(
            f"Câmera configurada: {actual_width}x{actual_height} @ {actual_fps:.1f} FPS"
        )
        
        return capture
    
    def _capture_loop(self):
        """Loop de captura executado em thread separada"""
        logger.debug("Thread de captura iniciada")
        
        while self._running:
            if self._capture is None:
                break
                
            ret, frame = self._capture.read()
            
            if not ret:
                logger.warning("Falha na leitura do frame")
                continue
            
            # Cria container do frame
            self._frame_count += 1
            frame_data = FrameData(
                frame=frame,
                timestamp=time.time(),
                frame_number=self._frame_count,
                resolution=(frame.shape[1], frame.shape[0])
            )
            
            # Atualiza último frame (thread-safe)
            with self._lock:
                self._last_frame = frame_data
            
            # Adiciona à fila (descarta frames antigos se necessário)
            if self._frame_queue.full():
                try:
                    self._frame_queue.get_nowait()
                except:
                    pass
            
            try:
                self._frame_queue.put_nowait(frame_data)
            except:
                pass
            
            # Callback
            if self.frame_callback:
                try:
                    self.frame_callback(frame_data)
                except Exception as e:
                    logger.error(f"Erro no callback de frame: {e}")
            
            # Atualiza FPS
            self._fps_counter += 1
            elapsed = time.time() - self._fps_timer
            if elapsed >= 1.0:
                self._fps_actual = self._fps_counter / elapsed
                self._fps_counter = 0
                self._fps_timer = time.time()
        
        logger.debug("Thread de captura finalizada")
    
    def start(self):
        """Inicia a captura de vídeo"""
        if self._running:
            logger.warning("Stream já está em execução")
            return
        
        try:
            self._capture = self._initialize_camera()
        except Exception as e:
            raise CameraInitializationError(f"Erro ao inicializar câmera: {e}")
        
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        
        logger.info("Stream de vídeo iniciado")
    
    def stop(self):
        """Para a captura de vídeo"""
        self._running = False
        
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        
        logger.info("Stream de vídeo parado")
    
    def read(self) -> Optional[FrameData]:
        """
        Lê o frame mais recente da fila.
        
        Returns:
            FrameData ou None se não houver frames disponíveis
        """
        try:
            return self._frame_queue.get_nowait()
        except:
            return None
    
    def read_latest(self) -> Optional[FrameData]:
        """
        Retorna o último frame capturado (sem fila).
        Útil para processamento onde só interessa o frame mais recente.
        
        Returns:
            FrameData ou None
        """
        with self._lock:
            return self._last_frame
    
    def capture_snapshot(self) -> Optional[np.ndarray]:
        """
        Captura um snapshot em alta resolução.
        
        Returns:
            Imagem numpy array em resolução completa
        """
        frame_data = self.read_latest()
        if frame_data is None:
            return None
        
        # Retorna cópia para evitar race conditions
        return frame_data.frame.copy()
    
    @property
    def is_running(self) -> bool:
        """Verifica se o stream está ativo"""
        return self._running
    
    @property
    def fps(self) -> float:
        """Retorna FPS atual"""
        return self._fps_actual
    
    @property
    def frame_count(self) -> int:
        """Retorna número total de frames capturados"""
        return self._frame_count
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class ImageLoader:
    """
    Classe para carregar e validar imagens estáticas.
    
    Uso:
        loader = ImageLoader()
        image = loader.load("caminho/para/imagem.jpg")
        
        if loader.validate_quality(image):
            # Processar imagem
    """
    
    SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
    MIN_RESOLUTION = (224, 224)
    MAX_RESOLUTION = (8192, 8192)
    
    @classmethod
    def load(cls, image_path: str) -> np.ndarray:
        """
        Carrega uma imagem do disco.
        
        Args:
            image_path: Caminho para o arquivo de imagem
            
        Returns:
            Imagem como numpy array (BGR)
            
        Raises:
            FileNotFoundError: Arquivo não encontrado
            ValueError: Formato não suportado ou imagem inválida
        """
        from pathlib import Path
        
        path = Path(image_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {image_path}")
        
        if path.suffix.lower() not in cls.SUPPORTED_FORMATS:
            raise ValueError(
                f"Formato não suportado: {path.suffix}. "
                f"Formatos aceitos: {cls.SUPPORTED_FORMATS}"
            )
        
        image = cv2.imread(str(path))
        
        if image is None:
            raise ValueError(f"Não foi possível ler a imagem: {image_path}")
        
        logger.info(f"Imagem carregada: {path.name} ({image.shape[1]}x{image.shape[0]})")
        
        return image
    
    @classmethod
    def validate_quality(
        cls,
        image: np.ndarray,
        min_resolution: Optional[Tuple[int, int]] = None,
        check_blur: bool = True,
        blur_threshold: float = 100.0
    ) -> Tuple[bool, str]:
        """
        Valida a qualidade de uma imagem para análise.
        
        Args:
            image: Imagem numpy array
            min_resolution: Resolução mínima (width, height)
            check_blur: Verificar se a imagem está borrada
            blur_threshold: Limiar de variância do Laplaciano
            
        Returns:
            Tupla (is_valid, message)
        """
        min_res = min_resolution or cls.MIN_RESOLUTION
        
        # Verifica resolução mínima
        height, width = image.shape[:2]
        if width < min_res[0] or height < min_res[1]:
            return False, f"Resolução muito baixa: {width}x{height}. Mínimo: {min_res}"
        
        # Verifica resolução máxima
        if width > cls.MAX_RESOLUTION[0] or height > cls.MAX_RESOLUTION[1]:
            return False, f"Resolução muito alta: {width}x{height}. Máximo: {cls.MAX_RESOLUTION}"
        
        # Verifica blur (foco)
        if check_blur:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            if laplacian_var < blur_threshold:
                return False, f"Imagem muito borrada (score: {laplacian_var:.1f} < {blur_threshold})"
        
        return True, "Imagem válida para análise"
    
    @classmethod
    def preprocess(
        cls,
        image: np.ndarray,
        target_size: Optional[Tuple[int, int]] = None,
        normalize: bool = True,
        to_rgb: bool = True
    ) -> np.ndarray:
        """
        Pré-processa imagem para inferência do modelo.
        
        Args:
            image: Imagem de entrada (BGR)
            target_size: Tamanho alvo (width, height)
            normalize: Normalizar para [0, 1]
            to_rgb: Converter BGR para RGB
            
        Returns:
            Imagem pré-processada
        """
        processed = image.copy()
        
        # Converte BGR para RGB
        if to_rgb:
            processed = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
        
        # Redimensiona mantendo aspect ratio (com padding se necessário)
        if target_size is not None:
            processed = cls._resize_with_padding(processed, target_size)
        
        # Normaliza
        if normalize:
            processed = processed.astype(np.float32) / 255.0
        
        return processed
    
    @staticmethod
    def _resize_with_padding(
        image: np.ndarray,
        target_size: Tuple[int, int],
        pad_color: Tuple[int, int, int] = (0, 0, 0)
    ) -> np.ndarray:
        """Redimensiona mantendo aspect ratio com padding"""
        target_w, target_h = target_size
        h, w = image.shape[:2]
        
        # Calcula escala mantendo aspect ratio
        scale = min(target_w / w, target_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        # Redimensiona
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # Cria imagem com padding
        padded = np.full((target_h, target_w, 3), pad_color, dtype=np.uint8)
        
        # Centraliza a imagem
        x_offset = (target_w - new_w) // 2
        y_offset = (target_h - new_h) // 2
        padded[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
        
        return padded
