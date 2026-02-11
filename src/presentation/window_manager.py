"""
REDISUS - Sistema de Diagnóstico de Feridas
Gerenciador de Janelas

Gerencia múltiplas janelas OpenCV de forma organizada:
- Janela principal de vídeo
- Janela de análise
- Janela de histórico
- Controles de teclado
"""
import cv2
import numpy as np
from typing import Dict, Optional, Callable, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class WindowType(Enum):
    """Tipos de janela"""
    MAIN = "main"
    ANALYSIS = "analysis"
    HISTORY = "history"
    SETTINGS = "settings"
    DEBUG = "debug"


@dataclass
class WindowConfig:
    """Configuração de uma janela"""
    name: str
    title: str
    width: int = 1280
    height: int = 720
    resizable: bool = True
    position: Optional[Tuple[int, int]] = None
    flags: int = cv2.WINDOW_NORMAL


@dataclass 
class KeyBinding:
    """Associação de tecla a ação"""
    key: int
    action: Callable
    description: str
    modifiers: List[str] = field(default_factory=list)


class WindowManager:
    """
    Gerenciador centralizado de janelas OpenCV.
    
    Características:
    - Gerencia ciclo de vida das janelas
    - Processa eventos de teclado
    - Suporta múltiplas janelas
    - Callbacks para eventos
    
    Uso:
        manager = WindowManager()
        manager.create_window("main", "REDISUS - Principal")
        
        while manager.is_running():
            frame = get_frame()
            manager.show("main", frame)
            
            key = manager.process_events()
            if key == ord('q'):
                break
                
        manager.cleanup()
    """
    
    def __init__(self):
        self._windows: Dict[str, WindowConfig] = {}
        self._key_bindings: Dict[int, KeyBinding] = {}
        self._running = True
        self._active_window: Optional[str] = None
        
        # Callbacks
        self._on_key_callbacks: List[Callable[[int], None]] = []
        self._on_mouse_callbacks: Dict[str, Callable] = {}
        
        # Histórico de frames para cada janela
        self._frame_history: Dict[str, List[np.ndarray]] = {}
        self._history_size = 30  # Frames
        
    def create_window(
        self,
        name: str,
        title: str = "",
        width: int = 1280,
        height: int = 720,
        resizable: bool = True,
        position: Optional[Tuple[int, int]] = None
    ) -> bool:
        """
        Cria uma nova janela.
        
        Args:
            name: Identificador único
            title: Título da janela
            width: Largura
            height: Altura
            resizable: Se pode redimensionar
            position: Posição (x, y) na tela
            
        Returns:
            True se criada com sucesso
        """
        if name in self._windows:
            logger.warning(f"Janela '{name}' já existe")
            return False
            
        title = title or name
        flags = cv2.WINDOW_NORMAL if resizable else cv2.WINDOW_AUTOSIZE
        
        config = WindowConfig(
            name=name,
            title=title,
            width=width,
            height=height,
            resizable=resizable,
            position=position,
            flags=flags
        )
        
        # Cria janela OpenCV
        cv2.namedWindow(title, flags)
        
        if resizable:
            cv2.resizeWindow(title, width, height)
            
        if position:
            cv2.moveWindow(title, position[0], position[1])
            
        self._windows[name] = config
        self._frame_history[name] = []
        
        if self._active_window is None:
            self._active_window = name
            
        logger.info(f"Janela criada: {title} ({width}x{height})")
        return True
    
    def show(
        self,
        name: str,
        frame: np.ndarray,
        save_history: bool = False
    ) -> bool:
        """
        Exibe frame em uma janela.
        
        Args:
            name: Nome da janela
            frame: Frame para exibir
            save_history: Se deve salvar no histórico
            
        Returns:
            True se exibido com sucesso
        """
        if name not in self._windows:
            logger.warning(f"Janela '{name}' não existe")
            return False
            
        config = self._windows[name]
        cv2.imshow(config.title, frame)
        
        if save_history:
            history = self._frame_history.get(name, [])
            history.append(frame.copy())
            if len(history) > self._history_size:
                history.pop(0)
            self._frame_history[name] = history
            
        return True
    
    def destroy(self, name: str):
        """Destrói uma janela"""
        if name in self._windows:
            config = self._windows[name]
            cv2.destroyWindow(config.title)
            del self._windows[name]
            logger.info(f"Janela destruída: {name}")
            
    def cleanup(self):
        """Limpa todas as janelas"""
        cv2.destroyAllWindows()
        self._windows.clear()
        self._running = False
        logger.info("Todas as janelas fechadas")
        
    def is_running(self) -> bool:
        """Verifica se o gerenciador está ativo"""
        return self._running
        
    def stop(self):
        """Para o gerenciador"""
        self._running = False
        
    def process_events(self, wait_ms: int = 1) -> int:
        """
        Processa eventos de teclado.
        
        Args:
            wait_ms: Tempo de espera em ms (0 = infinito)
            
        Returns:
            Código da tecla pressionada (-1 se nenhuma)
        """
        key = cv2.waitKey(wait_ms) & 0xFF
        
        if key == 255:  # Nenhuma tecla
            return -1
            
        # Verifica bindings
        if key in self._key_bindings:
            binding = self._key_bindings[key]
            try:
                binding.action()
            except Exception as e:
                logger.error(f"Erro no binding de tecla: {e}")
                
        # Callbacks gerais
        for callback in self._on_key_callbacks:
            try:
                callback(key)
            except Exception as e:
                logger.error(f"Erro no callback de tecla: {e}")
                
        return key
    
    def bind_key(
        self,
        key: str,
        action: Callable,
        description: str = ""
    ):
        """
        Associa uma ação a uma tecla.
        
        Args:
            key: Tecla (string ou código)
            action: Função a executar
            description: Descrição da ação
        """
        if isinstance(key, str):
            key_code = ord(key.lower())
        else:
            key_code = key
            
        self._key_bindings[key_code] = KeyBinding(
            key=key_code,
            action=action,
            description=description
        )
        
    def unbind_key(self, key: str):
        """Remove binding de tecla"""
        if isinstance(key, str):
            key = ord(key.lower())
        if key in self._key_bindings:
            del self._key_bindings[key]
            
    def on_key(self, callback: Callable[[int], None]):
        """Registra callback para eventos de tecla"""
        self._on_key_callbacks.append(callback)
        
    def set_mouse_callback(
        self,
        window_name: str,
        callback: Callable
    ):
        """
        Define callback de mouse para uma janela.
        
        Args:
            window_name: Nome da janela
            callback: Função callback(event, x, y, flags, param)
        """
        if window_name in self._windows:
            config = self._windows[window_name]
            cv2.setMouseCallback(config.title, callback)
            self._on_mouse_callbacks[window_name] = callback
            
    def get_frame_history(self, window_name: str) -> List[np.ndarray]:
        """Retorna histórico de frames de uma janela"""
        return self._frame_history.get(window_name, [])
    
    def get_last_frame(self, window_name: str) -> Optional[np.ndarray]:
        """Retorna último frame de uma janela"""
        history = self._frame_history.get(window_name, [])
        return history[-1] if history else None
    
    def get_bindings_help(self) -> str:
        """Retorna texto de ajuda com todos os bindings"""
        lines = ["Atalhos de teclado:", "=" * 30]
        
        for key_code, binding in sorted(self._key_bindings.items()):
            key_char = chr(key_code) if 32 <= key_code <= 126 else f"[{key_code}]"
            lines.append(f"  {key_char}: {binding.description}")
            
        return "\n".join(lines)
    
    def create_layout(
        self,
        layout: str = "single"
    ) -> Dict[str, Tuple[int, int]]:
        """
        Cria layout de janelas predefinido.
        
        Args:
            layout: Tipo de layout ("single", "split", "quad")
            
        Returns:
            Dict com posições das janelas
        """
        # Obtém resolução da tela (aproximação)
        screen_w, screen_h = 1920, 1080
        
        positions = {}
        
        if layout == "single":
            positions["main"] = (50, 50)
            
        elif layout == "split":
            half_w = screen_w // 2 - 20
            positions["main"] = (10, 50)
            positions["analysis"] = (half_w + 30, 50)
            
        elif layout == "quad":
            half_w = screen_w // 2 - 20
            half_h = screen_h // 2 - 50
            positions["main"] = (10, 10)
            positions["analysis"] = (half_w + 20, 10)
            positions["history"] = (10, half_h + 50)
            positions["debug"] = (half_w + 20, half_h + 50)
            
        return positions


class InteractiveOverlay:
    """
    Overlay interativo para seleção e anotação.
    
    Permite:
    - Seleção de região (ROI)
    - Anotações de texto
    - Pontos de medição
    """
    
    def __init__(self, window_manager: WindowManager):
        self.wm = window_manager
        
        # Estado de seleção
        self._selecting = False
        self._selection_start: Optional[Tuple[int, int]] = None
        self._selection_end: Optional[Tuple[int, int]] = None
        self._current_roi: Optional[Tuple[int, int, int, int]] = None
        
        # Anotações
        self._annotations: List[Dict] = []
        self._measurement_points: List[Tuple[int, int]] = []
        
    def enable_roi_selection(self, window_name: str, callback: Callable):
        """
        Habilita seleção de região de interesse.
        
        Args:
            window_name: Janela para seleção
            callback: Função chamada quando ROI selecionada (x, y, w, h)
        """
        def mouse_callback(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                self._selecting = True
                self._selection_start = (x, y)
                self._selection_end = (x, y)
                
            elif event == cv2.EVENT_MOUSEMOVE and self._selecting:
                self._selection_end = (x, y)
                
            elif event == cv2.EVENT_LBUTTONUP:
                self._selecting = False
                if self._selection_start and self._selection_end:
                    x1, y1 = self._selection_start
                    x2, y2 = self._selection_end
                    
                    # Normaliza coordenadas
                    x1, x2 = min(x1, x2), max(x1, x2)
                    y1, y2 = min(y1, y2), max(y1, y2)
                    
                    w, h = x2 - x1, y2 - y1
                    if w > 10 and h > 10:  # Mínimo 10x10
                        self._current_roi = (x1, y1, w, h)
                        callback(x1, y1, w, h)
                        
        self.wm.set_mouse_callback(window_name, mouse_callback)
        
    def draw_selection(self, frame: np.ndarray) -> np.ndarray:
        """Desenha seleção atual sobre o frame"""
        output = frame.copy()
        
        if self._selecting and self._selection_start and self._selection_end:
            cv2.rectangle(
                output,
                self._selection_start,
                self._selection_end,
                (0, 255, 0),
                2
            )
            
        if self._current_roi:
            x, y, w, h = self._current_roi
            cv2.rectangle(output, (x, y), (x + w, y + h), (0, 255, 255), 2)
            cv2.putText(
                output,
                f"ROI: {w}x{h}",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 255),
                1
            )
            
        return output
    
    def get_current_roi(self) -> Optional[Tuple[int, int, int, int]]:
        """Retorna ROI atual"""
        return self._current_roi
    
    def clear_roi(self):
        """Limpa ROI"""
        self._current_roi = None
        
    def add_measurement_point(self, x: int, y: int):
        """Adiciona ponto de medição"""
        self._measurement_points.append((x, y))
        
    def draw_measurements(self, frame: np.ndarray) -> np.ndarray:
        """Desenha pontos e linhas de medição"""
        output = frame.copy()
        
        for i, point in enumerate(self._measurement_points):
            cv2.circle(output, point, 5, (0, 255, 255), -1)
            cv2.putText(
                output,
                f"P{i+1}",
                (point[0] + 10, point[1]),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 255, 255),
                1
            )
            
        # Desenha linhas entre pontos consecutivos
        for i in range(1, len(self._measurement_points)):
            cv2.line(
                output,
                self._measurement_points[i-1],
                self._measurement_points[i],
                (0, 255, 255),
                2
            )
            
        return output
    
    def clear_measurements(self):
        """Limpa pontos de medição"""
        self._measurement_points.clear()
