"""
REDISUS - Treinamento de Rede Neural para Deteccao de Feridas
Dataset: Medetec Image Database

Este script treina um modelo de classificacao para distinguir:
1. Feridas reais (positivos)
2. Amostras negativas (pele saudavel, dedos, dispositivos, fundo)

Estrategias implementadas:
- Data augmentation agressivo
- Amostras negativas sinteticas
- Balanceamento de classes
- Validacao cruzada
"""
import os
import json
import random
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass
import argparse

import cv2
import numpy as np
from loguru import logger

# Tenta importar bibliotecas de ML
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, Model
    from tensorflow.keras.preprocessing.image import ImageDataGenerator
    from tensorflow.keras.callbacks import (
        ModelCheckpoint, EarlyStopping, ReduceLROnPlateau, TensorBoard
    )
    from tensorflow.keras.applications import EfficientNetB0, MobileNetV2
    HAS_TF = True
except ImportError:
    HAS_TF = False
    logger.warning("TensorFlow nao disponivel")

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader
    import torchvision.transforms as T
    from torchvision import models
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


@dataclass
class TrainingConfig:
    """Configuracao de treinamento"""
    # Paths
    dataset_path: str = "dataset/medetec"
    output_path: str = "models/wound_detector"
    negative_samples_path: str = "dataset/negative_samples"
    
    # Modelo
    model_type: str = "efficientnet"  # efficientnet, mobilenet, custom
    input_size: Tuple[int, int] = (224, 224)
    num_classes: int = 2  # wound, no_wound
    
    # Treinamento
    epochs: int = 50
    batch_size: int = 32
    learning_rate: float = 0.001
    validation_split: float = 0.2
    
    # Augmentation - reduzido para treinar mais rapido
    augmentation_factor: int = 2
    
    # Early stopping
    patience: int = 10
    
    # Hardware
    use_gpu: bool = True


class NegativeSampleGenerator:
    """
    Gerador de amostras negativas.
    
    Cria imagens sinteticas de:
    - Pele saudavel
    - Dedos
    - Dispositivos (bordas retas)
    - Fundos hospitalares
    """
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_skin_samples(self, count: int = 100) -> List[str]:
        """Gera amostras de pele saudavel"""
        samples = []
        
        for i in range(count):
            # Cria imagem com tom de pele
            h, w = random.randint(200, 400), random.randint(200, 400)
            
            # Base de pele (varia entre tons)
            skin_tone = random.choice([
                [180, 140, 120],  # Claro
                [150, 110, 90],   # Medio
                [100, 70, 50],    # Escuro
            ])
            
            image = np.ones((h, w, 3), dtype=np.uint8)
            image[:] = skin_tone
            
            # Adiciona variacao suave
            noise = np.random.randn(h, w, 3) * 10
            image = np.clip(image + noise, 0, 255).astype(np.uint8)
            
            # Suaviza
            image = cv2.GaussianBlur(image, (7, 7), 0)
            
            # Adiciona textura leve de pele
            texture = np.random.randn(h, w) * 5
            texture = cv2.GaussianBlur(texture.astype(np.float32), (3, 3), 0)
            for c in range(3):
                image[:, :, c] = np.clip(image[:, :, c] + texture, 0, 255)
            
            # Salva
            filename = f"skin_healthy_{i:04d}.jpg"
            filepath = self.output_dir / filename
            cv2.imwrite(str(filepath), image)
            samples.append(str(filepath))
            
        logger.info(f"Geradas {count} amostras de pele saudavel")
        return samples
    
    def generate_finger_samples(self, count: int = 100) -> List[str]:
        """Gera amostras sinteticas de dedos"""
        samples = []
        
        for i in range(count):
            # Imagem maior para caber dedo
            h, w = 300, 200
            
            # Fundo variado
            bg_color = random.choice([
                [200, 200, 200],  # Cinza claro
                [240, 240, 240],  # Branco
                [100, 100, 100],  # Cinza escuro
            ])
            image = np.ones((h, w, 3), dtype=np.uint8)
            image[:] = bg_color
            
            # Tom de pele do dedo
            skin_tone = random.choice([
                [180, 140, 120],
                [150, 110, 90],
                [100, 70, 50],
            ])
            
            # Desenha formato de dedo (elipse alongada)
            center = (w // 2, h // 2)
            axes = (random.randint(30, 50), random.randint(80, 130))
            angle = random.randint(-20, 20)
            
            # Cria mascara do dedo
            finger_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.ellipse(finger_mask, center, axes, angle, 0, 360, 255, -1)
            
            # Aplica cor de pele
            image[finger_mask > 0] = skin_tone
            
            # Adiciona unha (opcional)
            if random.random() > 0.3:
                nail_y = center[1] - axes[1] + 20
                nail_rect = (center[0] - 15, nail_y, 30, 25)
                cv2.rectangle(
                    image,
                    (nail_rect[0], nail_rect[1]),
                    (nail_rect[0] + nail_rect[2], nail_rect[1] + nail_rect[3]),
                    [220, 200, 200],
                    -1
                )
            
            # Adiciona ruido
            noise = np.random.randn(h, w, 3) * 8
            image = np.clip(image + noise, 0, 255).astype(np.uint8)
            image = cv2.GaussianBlur(image, (5, 5), 0)
            
            # Salva
            filename = f"finger_{i:04d}.jpg"
            filepath = self.output_dir / filename
            cv2.imwrite(str(filepath), image)
            samples.append(str(filepath))
            
        logger.info(f"Geradas {count} amostras de dedos")
        return samples
    
    def generate_device_samples(self, count: int = 50) -> List[str]:
        """Gera amostras de dispositivos/objetos"""
        samples = []
        
        for i in range(count):
            h, w = random.randint(200, 350), random.randint(150, 300)
            
            # Fundo
            image = np.ones((h, w, 3), dtype=np.uint8) * 200
            
            # Desenha forma geometrica (dispositivo)
            device_color = random.choice([
                [30, 30, 30],     # Preto
                [50, 50, 50],     # Cinza escuro
                [180, 180, 180],  # Metalico
            ])
            
            # Retangulo com cantos arredondados
            margin = 20
            cv2.rectangle(
                image,
                (margin, margin),
                (w - margin, h - margin),
                device_color,
                -1
            )
            
            # Adiciona borda/reflexo
            cv2.rectangle(
                image,
                (margin, margin),
                (w - margin, h - margin),
                [100, 100, 100],
                2
            )
            
            # Adiciona elementos de tela (linhas retas)
            if random.random() > 0.5:
                for _ in range(random.randint(2, 5)):
                    y = random.randint(margin + 10, h - margin - 10)
                    cv2.line(
                        image,
                        (margin + 10, y),
                        (w - margin - 10, y),
                        [60, 60, 60],
                        1
                    )
            
            # Salva
            filename = f"device_{i:04d}.jpg"
            filepath = self.output_dir / filename
            cv2.imwrite(str(filepath), image)
            samples.append(str(filepath))
            
        logger.info(f"Geradas {count} amostras de dispositivos")
        return samples
    
    def generate_all(self, skin_count: int = 100, finger_count: int = 100, device_count: int = 50):
        """Gera todas as amostras negativas"""
        all_samples = []
        all_samples.extend(self.generate_skin_samples(skin_count))
        all_samples.extend(self.generate_finger_samples(finger_count))
        all_samples.extend(self.generate_device_samples(device_count))
        return all_samples


class WoundDataAugmentor:
    """
    Augmentacao de dados para imagens de feridas.
    
    Aplica transformacoes que simulam variacoes reais:
    - Iluminacao
    - Rotacao/escala
    - Desfoque
    - Ruido
    """
    
    def __init__(self, output_size: Tuple[int, int] = (224, 224)):
        self.output_size = output_size
        
    def augment(self, image: np.ndarray, count: int = 5) -> List[np.ndarray]:
        """
        Gera versoes aumentadas da imagem.
        
        Args:
            image: Imagem original BGR
            count: Numero de augmentacoes
            
        Returns:
            Lista de imagens aumentadas
        """
        augmented = []
        
        for _ in range(count):
            aug_img = image.copy()
            
            # 1. Variacao de brilho
            if random.random() > 0.3:
                factor = random.uniform(0.7, 1.3)
                aug_img = np.clip(aug_img * factor, 0, 255).astype(np.uint8)
            
            # 2. Variacao de contraste
            if random.random() > 0.3:
                factor = random.uniform(0.8, 1.2)
                mean = np.mean(aug_img)
                aug_img = np.clip((aug_img - mean) * factor + mean, 0, 255).astype(np.uint8)
            
            # 3. Rotacao
            if random.random() > 0.3:
                angle = random.uniform(-30, 30)
                h, w = aug_img.shape[:2]
                M = cv2.getRotationMatrix2D((w/2, h/2), angle, 1.0)
                aug_img = cv2.warpAffine(aug_img, M, (w, h), borderMode=cv2.BORDER_REFLECT)
            
            # 4. Flip horizontal
            if random.random() > 0.5:
                aug_img = cv2.flip(aug_img, 1)
            
            # 5. Flip vertical
            if random.random() > 0.5:
                aug_img = cv2.flip(aug_img, 0)
            
            # 6. Desfoque
            if random.random() > 0.5:
                ksize = random.choice([3, 5, 7])
                aug_img = cv2.GaussianBlur(aug_img, (ksize, ksize), 0)
            
            # 7. Ruido
            if random.random() > 0.5:
                noise = np.random.randn(*aug_img.shape) * random.uniform(5, 15)
                aug_img = np.clip(aug_img + noise, 0, 255).astype(np.uint8)
            
            # 8. Escala
            if random.random() > 0.3:
                scale = random.uniform(0.8, 1.2)
                h, w = aug_img.shape[:2]
                new_h, new_w = int(h * scale), int(w * scale)
                aug_img = cv2.resize(aug_img, (new_w, new_h))
                
                # Crop ou pad para tamanho original
                if new_h > h:
                    start = (new_h - h) // 2
                    aug_img = aug_img[start:start+h, :, :]
                if new_w > w:
                    start = (new_w - w) // 2
                    aug_img = aug_img[:, start:start+w, :]
            
            # 9. Matiz/Saturacao
            if random.random() > 0.4:
                hsv = cv2.cvtColor(aug_img, cv2.COLOR_BGR2HSV).astype(np.float32)
                hsv[:, :, 0] += random.uniform(-10, 10)  # Hue
                hsv[:, :, 1] *= random.uniform(0.8, 1.2)  # Saturation
                hsv = np.clip(hsv, 0, 255).astype(np.uint8)
                aug_img = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
            
            # Redimensiona para tamanho de saida
            aug_img = cv2.resize(aug_img, self.output_size)
            
            augmented.append(aug_img)
            
        return augmented


class DatasetBuilder:
    """
    Construtor de dataset para treinamento.
    
    Organiza imagens em estrutura de pastas para Keras/PyTorch.
    """
    
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.augmentor = WoundDataAugmentor(config.input_size)
        
    def build_dataset(self) -> Tuple[str, str]:
        """
        Constroi dataset organizado.
        
        Returns:
            (train_dir, val_dir)
        """
        # Cria estrutura de diretorios
        output_base = Path(self.config.output_path) / "dataset"
        train_dir = output_base / "train"
        val_dir = output_base / "val"
        
        for split_dir in [train_dir, val_dir]:
            (split_dir / "wound").mkdir(parents=True, exist_ok=True)
            (split_dir / "no_wound").mkdir(parents=True, exist_ok=True)
        
        # Carrega imagens positivas (feridas do medetec)
        wound_images = self._load_wound_images()
        logger.info(f"Carregadas {len(wound_images)} imagens de feridas")
        
        # Gera/carrega amostras negativas
        negative_images = self._get_negative_samples()
        logger.info(f"Carregadas {len(negative_images)} amostras negativas")
        
        # Split train/val
        random.shuffle(wound_images)
        random.shuffle(negative_images)
        
        split_idx_wound = int(len(wound_images) * (1 - self.config.validation_split))
        split_idx_neg = int(len(negative_images) * (1 - self.config.validation_split))
        
        train_wounds = wound_images[:split_idx_wound]
        val_wounds = wound_images[split_idx_wound:]
        train_negatives = negative_images[:split_idx_neg]
        val_negatives = negative_images[split_idx_neg:]
        
        # Processa e salva
        self._process_and_save(train_wounds, train_dir / "wound", augment=True)
        self._process_and_save(val_wounds, val_dir / "wound", augment=False)
        self._process_and_save(train_negatives, train_dir / "no_wound", augment=True)
        self._process_and_save(val_negatives, val_dir / "no_wound", augment=False)
        
        # Conta imagens
        train_count = sum(1 for _ in (train_dir / "wound").iterdir()) + sum(1 for _ in (train_dir / "no_wound").iterdir())
        val_count = sum(1 for _ in (val_dir / "wound").iterdir()) + sum(1 for _ in (val_dir / "no_wound").iterdir())
        
        logger.info(f"Dataset criado: {train_count} train, {val_count} val")
        
        return str(train_dir), str(val_dir)
    
    def _load_wound_images(self) -> List[str]:
        """Carrega caminhos das imagens de feridas do medetec"""
        medetec_path = Path(self.config.dataset_path)
        images = []
        
        # Extensoes validas
        extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        
        for category_dir in medetec_path.iterdir():
            if category_dir.is_dir():
                for img_path in category_dir.iterdir():
                    if img_path.suffix.lower() in extensions:
                        images.append(str(img_path))
                        
        return images
    
    def _get_negative_samples(self) -> List[str]:
        """Obtem amostras negativas (gera se necessario)"""
        neg_path = Path(self.config.negative_samples_path)
        
        if not neg_path.exists() or len(list(neg_path.iterdir())) < 50:
            # Gera amostras negativas
            generator = NegativeSampleGenerator(str(neg_path))
            return generator.generate_all(
                skin_count=150,
                finger_count=150,
                device_count=100
            )
        else:
            # Carrega existentes
            extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
            return [str(p) for p in neg_path.iterdir() if p.suffix.lower() in extensions]
    
    def _process_and_save(
        self,
        image_paths: List[str],
        output_dir: Path,
        augment: bool = False
    ):
        """Processa imagens e salva no diretorio"""
        for i, img_path in enumerate(image_paths):
            try:
                img = cv2.imread(img_path)
                if img is None:
                    continue
                    
                # Redimensiona
                img = cv2.resize(img, self.config.input_size)
                
                # Salva original
                base_name = Path(img_path).stem
                output_path = output_dir / f"{base_name}_{i:04d}.jpg"
                cv2.imwrite(str(output_path), img)
                
                # Augmentation
                if augment:
                    aug_images = self.augmentor.augment(img, self.config.augmentation_factor)
                    for j, aug_img in enumerate(aug_images):
                        aug_path = output_dir / f"{base_name}_{i:04d}_aug{j}.jpg"
                        cv2.imwrite(str(aug_path), aug_img)
                        
            except Exception as e:
                logger.warning(f"Erro processando {img_path}: {e}")


class WoundClassifierTrainer:
    """
    Treinador do modelo de classificacao.
    
    Treina modelo para distinguir feridas de nao-feridas.
    """
    
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.model = None
        self.history = None
        
    def build_model(self) -> Model:
        """Constroi modelo de classificacao"""
        if not HAS_TF:
            raise RuntimeError("TensorFlow necessario para treinamento")
            
        input_shape = (*self.config.input_size, 3)
        
        if self.config.model_type == "efficientnet":
            base_model = EfficientNetB0(
                weights='imagenet',
                include_top=False,
                input_shape=input_shape
            )
        elif self.config.model_type == "mobilenet":
            base_model = MobileNetV2(
                weights='imagenet',
                include_top=False,
                input_shape=input_shape
            )
        else:
            # Modelo custom simples
            base_model = self._build_custom_base(input_shape)
            
        # Congela base para transfer learning
        base_model.trainable = False
        
        # Adiciona cabeca de classificacao
        inputs = keras.Input(shape=input_shape)
        x = base_model(inputs, training=False)
        x = layers.GlobalAveragePooling2D()(x)
        x = layers.Dropout(0.3)(x)
        x = layers.Dense(256, activation='relu')(x)
        x = layers.Dropout(0.3)(x)
        x = layers.Dense(128, activation='relu')(x)
        outputs = layers.Dense(self.config.num_classes, activation='softmax')(x)
        
        self.model = Model(inputs, outputs)
        
        # Compila
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.config.learning_rate),
            loss='categorical_crossentropy',
            metrics=['accuracy', keras.metrics.Precision(), keras.metrics.Recall()]
        )
        
        logger.info(f"Modelo construido: {self.config.model_type}")
        self.model.summary()
        
        return self.model
    
    def _build_custom_base(self, input_shape):
        """Constroi modelo base customizado"""
        inputs = keras.Input(shape=input_shape)
        
        x = layers.Conv2D(32, 3, padding='same', activation='relu')(inputs)
        x = layers.BatchNormalization()(x)
        x = layers.MaxPooling2D()(x)
        
        x = layers.Conv2D(64, 3, padding='same', activation='relu')(x)
        x = layers.BatchNormalization()(x)
        x = layers.MaxPooling2D()(x)
        
        x = layers.Conv2D(128, 3, padding='same', activation='relu')(x)
        x = layers.BatchNormalization()(x)
        x = layers.MaxPooling2D()(x)
        
        x = layers.Conv2D(256, 3, padding='same', activation='relu')(x)
        x = layers.BatchNormalization()(x)
        x = layers.MaxPooling2D()(x)
        
        return Model(inputs, x)
    
    def train(self, train_dir: str, val_dir: str):
        """Treina o modelo"""
        if self.model is None:
            self.build_model()
            
        # Data generators com augmentation adicional
        train_datagen = ImageDataGenerator(
            rescale=1./255,
            rotation_range=20,
            width_shift_range=0.2,
            height_shift_range=0.2,
            horizontal_flip=True,
            vertical_flip=True,
            zoom_range=0.2,
            brightness_range=[0.8, 1.2]
        )
        
        val_datagen = ImageDataGenerator(rescale=1./255)
        
        train_generator = train_datagen.flow_from_directory(
            train_dir,
            target_size=self.config.input_size,
            batch_size=self.config.batch_size,
            class_mode='categorical',
            shuffle=True
        )
        
        val_generator = val_datagen.flow_from_directory(
            val_dir,
            target_size=self.config.input_size,
            batch_size=self.config.batch_size,
            class_mode='categorical',
            shuffle=False
        )
        
        # Callbacks
        output_dir = Path(self.config.output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        callbacks = [
            ModelCheckpoint(
                str(output_dir / "best_model.keras"),
                monitor='val_accuracy',
                save_best_only=True,
                mode='max'
            ),
            EarlyStopping(
                monitor='val_loss',
                patience=self.config.patience,
                restore_best_weights=True
            ),
            ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=5,
                min_lr=1e-7
            ),
            TensorBoard(
                log_dir=str(output_dir / "logs" / datetime.now().strftime("%Y%m%d-%H%M%S"))
            )
        ]
        
        # Calcula class weights para balanceamento
        class_counts = [
            len(list((Path(train_dir) / "wound").iterdir())),
            len(list((Path(train_dir) / "no_wound").iterdir()))
        ]
        total = sum(class_counts)
        class_weights = {i: total / (2 * count) for i, count in enumerate(class_counts)}
        
        logger.info(f"Class weights: {class_weights}")
        
        # Treina
        self.history = self.model.fit(
            train_generator,
            epochs=self.config.epochs,
            validation_data=val_generator,
            callbacks=callbacks,
            class_weight=class_weights
        )
        
        # Salva modelo final
        self.model.save(str(output_dir / "wound_detector_final.keras"))
        
        # Salva historico
        history_path = output_dir / "training_history.json"
        with open(history_path, 'w') as f:
            json.dump({k: [float(v) for v in vals] for k, vals in self.history.history.items()}, f)
            
        logger.info(f"Treinamento completo. Modelo salvo em {output_dir}")
        
        return self.history
    
    def fine_tune(self, train_dir: str, val_dir: str, unfreeze_layers: int = 20):
        """Fine-tuning do modelo pre-treinado"""
        if self.model is None:
            raise RuntimeError("Modelo nao carregado")
            
        # Descongela ultimas camadas
        base_model = self.model.layers[1]
        base_model.trainable = True
        
        for layer in base_model.layers[:-unfreeze_layers]:
            layer.trainable = False
            
        # Recompila com learning rate menor
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.config.learning_rate / 10),
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        logger.info(f"Fine-tuning com {unfreeze_layers} camadas descongeladas")
        
        # Treina novamente
        return self.train(train_dir, val_dir)


def main():
    """Funcao principal de treinamento"""
    parser = argparse.ArgumentParser(description="Treinar modelo de deteccao de feridas")
    
    parser.add_argument("--dataset", type=str, default="dataset/medetec",
                       help="Caminho para dataset medetec")
    parser.add_argument("--output", type=str, default="models/wound_detector",
                       help="Diretorio de saida")
    parser.add_argument("--model", type=str, default="efficientnet",
                       choices=["efficientnet", "mobilenet", "custom"],
                       help="Tipo de modelo")
    parser.add_argument("--epochs", type=int, default=50,
                       help="Numero de epochs")
    parser.add_argument("--batch-size", type=int, default=32,
                       help="Tamanho do batch")
    parser.add_argument("--lr", type=float, default=0.001,
                       help="Learning rate")
    parser.add_argument("--generate-negatives", action="store_true",
                       help="Gerar amostras negativas")
    parser.add_argument("--fine-tune", action="store_true",
                       help="Fazer fine-tuning apos treinamento inicial")
    
    args = parser.parse_args()
    
    # Configuracao
    config = TrainingConfig(
        dataset_path=args.dataset,
        output_path=args.output,
        model_type=args.model,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr
    )
    
    logger.info("=== REDISUS - Treinamento de Modelo ===")
    logger.info(f"Dataset: {config.dataset_path}")
    logger.info(f"Modelo: {config.model_type}")
    
    # Gera amostras negativas se solicitado
    if args.generate_negatives:
        generator = NegativeSampleGenerator(config.negative_samples_path)
        generator.generate_all()
    
    # Constroi dataset
    builder = DatasetBuilder(config)
    train_dir, val_dir = builder.build_dataset()
    
    # Treina
    if HAS_TF:
        trainer = WoundClassifierTrainer(config)
        trainer.build_model()
        trainer.train(train_dir, val_dir)
        
        if args.fine_tune:
            trainer.fine_tune(train_dir, val_dir)
    else:
        logger.error("TensorFlow necessario para treinamento")
        
    logger.info("=== Treinamento Concluido ===")


if __name__ == "__main__":
    main()
