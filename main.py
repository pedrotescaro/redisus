"""
REDISUS - Sistema de Diagnóstico de Feridas
Pipeline Principal Integrado v3.0

Este arquivo contém o pipeline completo que integra todos os módulos:
- Captura de vídeo em tempo real
- Detecção de feridas (YOLO)
- Segmentação de tecidos (U-Net + HSV/LAB multi-espaço)
- Classificação etiológica de dois estágios (ResNet50):
    * Estágio 1: Normal vs. Ferida
    * Estágio 2: Diabética / Pressão / Venosa
- Explicabilidade via Grad-CAM (layer4 ResNet50)
- Recomendação de tratamento
- Tracking de evolução

Uso:
    python main.py --mode webcam
    python main.py --mode image --input foto.jpg
    python main.py --mode demo
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from loguru import logger

from packages.shared.runtime import ensure_project_root_on_path

ensure_project_root_on_path()

from src.core.config import config, EtiologyType, ETIOLOGY_NAMES
from src.capture.video_stream import VideoStream, ImageLoader, FrameData
from src.detection.realtime_detector import RealtimeWoundDetector, Detection
from src.diagnosis.wound_analyzer import WoundAnalyzer, WoundAnalysisResult
from src.treatment.recommender import TreatmentRecommender
from src.treatment.evolution_tracker import EvolutionTracker


class RedisusApp:
    """
    Aplicação principal do REDISUS.
    
    Modos de operação:
    - webcam: Captura em tempo real com detecção e análise
    - image: Análise de imagem estática
    - demo: Demonstração com imagem de exemplo
    """
    
    def __init__(self):
        # Módulos
        self.detector: Optional[RealtimeWoundDetector] = None
        self.analyzer: Optional[WoundAnalyzer] = None
        self.recommender: Optional[TreatmentRecommender] = None
        self.tracker: Optional[EvolutionTracker] = None
        
        # Estado
        self.running = False
        self.last_snapshot: Optional[np.ndarray] = None
        self.last_analysis: Optional[WoundAnalysisResult] = None
        
        # Configuração de logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Configura sistema de logging"""
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
            level="INFO"
        )
        logger.add(
            "logs/redisus_{time}.log",
            rotation="10 MB",
            level="DEBUG"
        )
    
    def initialize(self, mode: str = "webcam"):
        """
        Inicializa módulos necessários para o modo especificado.
        
        Args:
            mode: "webcam", "image" ou "demo"
        """
        logger.info(f"Inicializando REDISUS no modo: {mode}")
        
        # Detector em tempo real (sempre para webcam)
        if mode == "webcam":
            self.detector = RealtimeWoundDetector(
                auto_capture_threshold=0.85,
                auto_capture_frames=15
            )
            self.detector.start()
        
        # Analisador (sempre necessário)
        self.analyzer = WoundAnalyzer(parallel=True)
        self.analyzer.load_models()
        
        # Recomendador
        self.recommender = TreatmentRecommender()
        
        # Tracker (para modo com paciente)
        self.tracker = EvolutionTracker(patient_id="demo_patient")
        
        logger.info("Inicialização completa")
    
    def run_webcam_mode(self, camera_id: int = 0):
        """
        Executa modo webcam com detecção em tempo real.
        
        Teclas:
        - SPACE: Capturar snapshot e analisar
        - A: Análise automática (quando detector indicar)
        - S: Salvar imagem
        - Q ou ESC: Sair
        """
        logger.info("Iniciando modo webcam...")
        logger.info("Pressione SPACE para capturar, Q para sair")
        
        stream = VideoStream(camera_id=camera_id)
        stream.start()
        
        self.running = True
        auto_capture = False
        
        # Janela
        window_name = "REDISUS - Deteccao de Feridas"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        
        try:
            while self.running:
                # Lê frame mais recente
                frame_data = stream.read_latest()
                
                if frame_data is None:
                    time.sleep(0.01)
                    continue
                
                frame = frame_data.frame
                
                # Processa com detector em tempo real
                annotated_frame, detections = self.detector.process_frame(frame)
                
                # Verifica auto-capture
                if auto_capture and self.detector.should_capture():
                    logger.info("Auto-capture ativado!")
                    self._capture_and_analyze(frame)
                    self.detector.reset_capture_trigger()
                
                # Adiciona instruções na tela
                self._draw_instructions(annotated_frame, auto_capture)
                
                # Exibe
                cv2.imshow(window_name, annotated_frame)
                
                # Processa teclas
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q') or key == 27:  # Q ou ESC
                    self.running = False
                
                elif key == ord(' '):  # SPACE - captura manual
                    self._capture_and_analyze(frame)
                
                elif key == ord('a'):  # A - toggle auto-capture
                    auto_capture = not auto_capture
                    logger.info(f"Auto-capture: {'ON' if auto_capture else 'OFF'}")
                
                elif key == ord('s'):  # S - salvar imagem
                    self._save_image(frame)
        
        except KeyboardInterrupt:
            logger.info("Interrompido pelo usuário")
        
        finally:
            stream.stop()
            cv2.destroyAllWindows()
    
    def _capture_and_analyze(self, frame: np.ndarray):
        """Captura snapshot e realiza análise completa"""
        logger.info("Capturando e analisando...")
        
        self.last_snapshot = frame.copy()
        
        # Análise completa
        result, visualization = self.analyzer.analyze_with_visualization(frame)
        self.last_analysis = result
        
        # Exibe resultado em nova janela
        cv2.imshow("REDISUS - Analise", visualization)
        
        # Log do resultado
        logger.info(f"Etiologia: {result.classification.primary_prediction.class_name} "
                   f"({result.classification.primary_prediction.confidence:.1%})")
        
        # Gera recomendação
        etiology = result.classification.primary_prediction.etiology_type
        recommendation = self.recommender.recommend(
            etiology=etiology,
            tissue_percentages=result.segmentation.tissue_percentages,
            confidence=result.classification.primary_prediction.confidence
        )
        
        # Exibe no console
        print("\n" + "=" * 60)
        print(result.get_summary())
        print("\n" + recommendation.primary_protocol.get_summary())
        print("=" * 60 + "\n")
        
        # Adiciona ao tracker
        self.tracker.add_measurement(
            segmentation=result.segmentation,
            notes=f"Etiologia: {result.classification.primary_prediction.class_name}"
        )
    
    def _draw_instructions(self, frame: np.ndarray, auto_capture: bool):
        """Desenha instruções na tela"""
        h, w = frame.shape[:2]
        
        instructions = [
            "SPACE: Capturar e Analisar",
            f"A: Auto-capture {'[ON]' if auto_capture else '[OFF]'}",
            "S: Salvar imagem",
            "Q/ESC: Sair"
        ]
        
        # Background semi-transparente
        overlay = frame.copy()
        cv2.rectangle(overlay, (w - 250, h - 100), (w - 10, h - 10), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        
        for i, text in enumerate(instructions):
            cv2.putText(
                frame,
                text,
                (w - 240, h - 80 + i * 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )
    
    def _save_image(self, frame: np.ndarray):
        """Salva imagem capturada"""
        output_dir = Path("output/captures")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_dir / f"capture_{timestamp}.jpg"
        
        cv2.imwrite(str(filename), frame)
        logger.info(f"Imagem salva: {filename}")
    
    def run_image_mode(self, image_path: str):
        """
        Executa análise em imagem estática.
        
        Args:
            image_path: Caminho para a imagem
        """
        logger.info(f"Analisando imagem: {image_path}")
        
        # Carrega imagem
        try:
            image = ImageLoader.load(image_path)
        except Exception as e:
            logger.error(f"Erro ao carregar imagem: {e}")
            return
        
        # Valida qualidade
        is_valid, message = ImageLoader.validate_quality(image)
        if not is_valid:
            logger.warning(f"Aviso de qualidade: {message}")
        
        # Análise
        result, visualization = self.analyzer.analyze_with_visualization(image)
        self.last_analysis = result
        
        # Exibe resultado
        print("\n" + result.get_summary())
        
        # Recomendação
        etiology = result.classification.primary_prediction.etiology_type
        recommendation = self.recommender.recommend(
            etiology=etiology,
            tissue_percentages=result.segmentation.tissue_percentages,
            confidence=result.classification.primary_prediction.confidence
        )
        print("\n" + recommendation.primary_protocol.get_summary())
        
        # Exibe visualização
        cv2.imshow("REDISUS - Analise", visualization)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        # Salva resultado
        output_path = Path(image_path).stem + "_analysis.jpg"
        cv2.imwrite(output_path, visualization)
        logger.info(f"Resultado salvo: {output_path}")
    
    def run_demo_mode(self):
        """
        Executa demonstração com imagem sintética.
        """
        logger.info("Executando modo demonstração...")
        
        # Cria imagem de demonstração
        demo_image = self._create_demo_image()
        
        # Análise
        result, visualization = self.analyzer.analyze_with_visualization(demo_image)
        
        # Exibe
        print("\n" + "=" * 60)
        print("MODO DEMONSTRAÇÃO")
        print("=" * 60)
        print(result.get_summary())
        
        # Recomendação
        etiology = result.classification.primary_prediction.etiology_type
        recommendation = self.recommender.recommend(
            etiology=etiology,
            tissue_percentages=result.segmentation.tissue_percentages,
            confidence=result.classification.primary_prediction.confidence
        )
        print("\n" + recommendation.primary_protocol.get_summary())
        
        # Exibe
        cv2.imshow("REDISUS - Demo", visualization)
        logger.info("Pressione qualquer tecla para sair...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    
    def _create_demo_image(self) -> np.ndarray:
        """Cria imagem sintética para demonstração"""
        # Imagem base (pele)
        image = np.ones((600, 800, 3), dtype=np.uint8)
        image[:, :] = (180, 160, 150)  # Tom de pele em BGR
        
        # Adiciona textura
        noise = np.random.randint(-20, 20, image.shape, dtype=np.int16)
        image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        # Área da "ferida" (elipse no centro)
        center = (400, 300)
        axes = (120, 80)
        
        # Granulação (vermelho)
        cv2.ellipse(image, center, axes, 0, 0, 360, (80, 80, 200), -1)
        
        # Esfacelo (amarelo) - parte menor
        cv2.ellipse(image, (420, 310), (50, 30), 30, 0, 360, (100, 200, 220), -1)
        
        # Necrose (escuro) - pequena área
        cv2.ellipse(image, (370, 280), (25, 15), -20, 0, 360, (40, 40, 50), -1)
        
        # Suaviza bordas
        image = cv2.GaussianBlur(image, (5, 5), 0)
        
        return image


def main():
    """Ponto de entrada principal"""
    parser = argparse.ArgumentParser(
        description="REDISUS - Sistema de Diagnóstico de Feridas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python main.py --mode webcam          # Inicia com webcam
  python main.py --mode webcam --camera 1  # Usa câmera secundária
  python main.py --mode image --input foto.jpg  # Analisa imagem
  python main.py --mode demo            # Executa demonstração
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["webcam", "image", "demo"],
        default="demo",
        help="Modo de operação (default: demo)"
    )
    
    parser.add_argument(
        "--input",
        type=str,
        help="Caminho da imagem para análise (modo image)"
    )
    
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="ID da câmera (default: 0)"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default="output",
        help="Diretório de saída"
    )
    
    args = parser.parse_args()
    
    # Cria diretório de saída
    Path(args.output).mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)
    
    # Inicializa e executa
    app = RedisusApp()
    
    try:
        if args.mode == "webcam":
            app.initialize(mode="webcam")
            app.run_webcam_mode(camera_id=args.camera)
        
        elif args.mode == "image":
            if not args.input:
                logger.error("Modo 'image' requer --input com caminho da imagem")
                sys.exit(1)
            
            if not Path(args.input).exists():
                logger.error(f"Arquivo não encontrado: {args.input}")
                sys.exit(1)
            
            app.initialize(mode="image")
            app.run_image_mode(args.input)
        
        elif args.mode == "demo":
            app.initialize(mode="demo")
            app.run_demo_mode()
    
    except Exception as e:
        logger.exception(f"Erro fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
