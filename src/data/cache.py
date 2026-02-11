"""
REDISUS - Sistema de Diagnóstico de Feridas
Módulo de Cache

Implementa caching para otimização de performance:
- Cache de frames para reduzir latência
- Cache de resultados para evitar reprocessamento
"""
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime

import numpy as np
from loguru import logger


@dataclass
class CacheEntry:
    """Entrada no cache"""
    key: str
    data: Any
    timestamp: float
    size_bytes: int = 0
    hit_count: int = 0


class FrameCache:
    """
    Cache de frames para processamento em tempo real.
    
    Mantém buffer circular de frames recentes para:
    - Reduzir latência de captura
    - Permitir processamento assíncrono
    - Suportar replay/revisão
    
    Thread-safe.
    
    Uso:
        cache = FrameCache(max_frames=30)
        cache.add(frame)
        
        # Obtém frame mais recente
        latest = cache.get_latest()
        
        # Obtém histórico
        history = cache.get_history(n=10)
    """
    
    def __init__(
        self,
        max_frames: int = 30,
        max_memory_mb: int = 512
    ):
        """
        Args:
            max_frames: Número máximo de frames no cache
            max_memory_mb: Limite de memória em MB
        """
        self.max_frames = max_frames
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        
        self._buffer: deque = deque(maxlen=max_frames)
        self._timestamps: deque = deque(maxlen=max_frames)
        self._lock = threading.RLock()
        self._current_size = 0
        
        # Métricas
        self._total_added = 0
        self._total_retrieved = 0
        
    def add(self, frame: np.ndarray, timestamp: Optional[float] = None) -> bool:
        """
        Adiciona frame ao cache.
        
        Args:
            frame: Frame (numpy array)
            timestamp: Timestamp opcional
            
        Returns:
            True se adicionado com sucesso
        """
        if frame is None:
            return False
            
        frame_size = frame.nbytes
        
        with self._lock:
            # Verifica limite de memória
            while self._current_size + frame_size > self.max_memory_bytes and self._buffer:
                old_frame = self._buffer.popleft()
                self._timestamps.popleft()
                self._current_size -= old_frame.nbytes
                
            # Adiciona novo frame
            self._buffer.append(frame.copy())
            self._timestamps.append(timestamp or time.time())
            self._current_size += frame_size
            self._total_added += 1
            
        return True
    
    def get_latest(self) -> Optional[Tuple[np.ndarray, float]]:
        """
        Retorna frame mais recente.
        
        Returns:
            Tuple (frame, timestamp) ou None
        """
        with self._lock:
            if self._buffer:
                self._total_retrieved += 1
                return self._buffer[-1].copy(), self._timestamps[-1]
            return None
    
    def get_history(self, n: int = 10) -> List[Tuple[np.ndarray, float]]:
        """
        Retorna últimos N frames.
        
        Args:
            n: Número de frames
            
        Returns:
            Lista de (frame, timestamp)
        """
        with self._lock:
            n = min(n, len(self._buffer))
            result = []
            for i in range(n):
                idx = -(i + 1)
                result.append((self._buffer[idx].copy(), self._timestamps[idx]))
            self._total_retrieved += n
            return result[::-1]  # Ordem cronológica
    
    def get_at_index(self, index: int) -> Optional[Tuple[np.ndarray, float]]:
        """Retorna frame em índice específico"""
        with self._lock:
            if 0 <= index < len(self._buffer):
                return self._buffer[index].copy(), self._timestamps[index]
            return None
    
    def clear(self):
        """Limpa o cache"""
        with self._lock:
            self._buffer.clear()
            self._timestamps.clear()
            self._current_size = 0
            
    @property
    def size(self) -> int:
        """Número de frames no cache"""
        return len(self._buffer)
    
    @property
    def memory_usage_mb(self) -> float:
        """Uso de memória em MB"""
        return self._current_size / (1024 * 1024)
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do cache"""
        return {
            "frames": len(self._buffer),
            "max_frames": self.max_frames,
            "memory_mb": round(self.memory_usage_mb, 2),
            "max_memory_mb": self.max_memory_bytes / (1024 * 1024),
            "total_added": self._total_added,
            "total_retrieved": self._total_retrieved
        }


class ResultCache:
    """
    Cache de resultados de análise.
    
    Evita reprocessamento de frames já analisados usando
    hash do frame como chave.
    
    Recursos:
    - TTL (Time To Live) configurável
    - Limite de memória
    - Invalidação automática
    
    Uso:
        cache = ResultCache(ttl_seconds=60)
        
        # Tenta obter do cache
        result = cache.get(frame_hash)
        if result is None:
            result = analyze(frame)
            cache.set(frame_hash, result)
    """
    
    def __init__(
        self,
        max_entries: int = 100,
        ttl_seconds: float = 60.0,
        max_memory_mb: int = 256
    ):
        """
        Args:
            max_entries: Número máximo de entradas
            ttl_seconds: Tempo de vida em segundos
            max_memory_mb: Limite de memória
        """
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        
        # Métricas
        self._hits = 0
        self._misses = 0
        
    def get(self, key: str) -> Optional[Any]:
        """
        Obtém valor do cache.
        
        Args:
            key: Chave (hash do frame ou ID)
            
        Returns:
            Valor ou None se não encontrado/expirado
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
                
            entry = self._cache[key]
            
            # Verifica TTL
            if time.time() - entry.timestamp > self.ttl_seconds:
                del self._cache[key]
                self._misses += 1
                return None
                
            entry.hit_count += 1
            self._hits += 1
            return entry.data
    
    def set(self, key: str, value: Any, size_bytes: int = 0) -> bool:
        """
        Armazena valor no cache.
        
        Args:
            key: Chave
            value: Valor a armazenar
            size_bytes: Tamanho estimado em bytes
            
        Returns:
            True se armazenado com sucesso
        """
        with self._lock:
            # Limpa entradas antigas se necessário
            self._cleanup()
            
            # Remove se já existe
            if key in self._cache:
                del self._cache[key]
                
            # Verifica limite de entradas
            while len(self._cache) >= self.max_entries:
                self._evict_oldest()
                
            # Cria entrada
            entry = CacheEntry(
                key=key,
                data=value,
                timestamp=time.time(),
                size_bytes=size_bytes
            )
            
            self._cache[key] = entry
            return True
    
    def invalidate(self, key: str) -> bool:
        """Remove entrada específica"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self):
        """Limpa todo o cache"""
        with self._lock:
            self._cache.clear()
            
    def _cleanup(self):
        """Remove entradas expiradas"""
        current_time = time.time()
        expired = [
            key for key, entry in self._cache.items()
            if current_time - entry.timestamp > self.ttl_seconds
        ]
        for key in expired:
            del self._cache[key]
            
    def _evict_oldest(self):
        """Remove entrada mais antiga"""
        if not self._cache:
            return
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].timestamp)
        del self._cache[oldest_key]
    
    @property
    def hit_rate(self) -> float:
        """Taxa de acerto do cache"""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas"""
        return {
            "entries": len(self._cache),
            "max_entries": self.max_entries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self.hit_rate:.1%}",
            "ttl_seconds": self.ttl_seconds
        }


def compute_frame_hash(frame: np.ndarray) -> str:
    """
    Computa hash rápido de um frame.
    
    Usa downsampling e hash simples para performance.
    
    Args:
        frame: Frame numpy
        
    Returns:
        String hash
    """
    # Downscale para 32x32
    small = frame[::frame.shape[0]//32, ::frame.shape[1]//32] if frame.shape[0] > 32 else frame
    
    # Calcula hash simples baseado em valores médios
    if len(small.shape) == 3:
        values = small.mean(axis=2).flatten()
    else:
        values = small.flatten()
        
    # Cria hash baseado em binning
    bins = (values // 16).astype(np.uint8)
    hash_bytes = bins.tobytes()
    
    # Usa hash built-in
    return format(hash(hash_bytes) & 0xFFFFFFFFFFFFFFFF, 'x')


class AnalysisQueue:
    """
    Fila de análises pendentes.
    
    Gerencia processamento assíncrono de frames.
    """
    
    def __init__(self, max_size: int = 10):
        self.max_size = max_size
        self._queue: deque = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._results: Dict[str, Any] = {}
        
    def add(self, frame_id: str, frame: np.ndarray) -> bool:
        """Adiciona frame para processamento"""
        with self._lock:
            if len(self._queue) >= self.max_size:
                return False
            self._queue.append((frame_id, frame.copy()))
            return True
    
    def get_pending(self) -> Optional[Tuple[str, np.ndarray]]:
        """Obtém próximo frame pendente"""
        with self._lock:
            if self._queue:
                return self._queue.popleft()
            return None
    
    def set_result(self, frame_id: str, result: Any):
        """Define resultado de análise"""
        with self._lock:
            self._results[frame_id] = result
            
    def get_result(self, frame_id: str) -> Optional[Any]:
        """Obtém resultado se disponível"""
        with self._lock:
            return self._results.pop(frame_id, None)
    
    @property
    def pending_count(self) -> int:
        return len(self._queue)
