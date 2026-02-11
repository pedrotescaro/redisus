"""
REDISUS - Treinamento Rapido de Rede Neural
Script simplificado para treinar modelo de deteccao de feridas

Usa apenas augmentation online do Keras (mais rapido)
"""
import os
import sys
from pathlib import Path
from datetime import datetime
import json

import cv2
import numpy as np
from loguru import logger

# TensorFlow
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, Model
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.applications import MobileNetV2

# Configuracao
DATASET_PATH = "dataset/medetec"
NEGATIVE_PATH = "dataset/negative_samples"
OUTPUT_PATH = "models/wound_detector"
INPUT_SIZE = (224, 224)
EPOCHS = 15
BATCH_SIZE = 16
LEARNING_RATE = 0.001


def prepare_dataset():
    """Prepara dataset de forma rapida (sem augmentation offline)"""
    train_dir = Path(OUTPUT_PATH) / "dataset_simple" / "train"
    val_dir = Path(OUTPUT_PATH) / "dataset_simple" / "val"
    
    # Cria diretorios
    for split in [train_dir, val_dir]:
        (split / "wound").mkdir(parents=True, exist_ok=True)
        (split / "no_wound").mkdir(parents=True, exist_ok=True)
    
    # Carrega imagens de feridas
    medetec = Path(DATASET_PATH)
    wound_images = []
    for category in medetec.iterdir():
        if category.is_dir():
            for img_path in category.iterdir():
                if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                    wound_images.append(img_path)
    
    logger.info(f"Encontradas {len(wound_images)} imagens de feridas")
    
    # Carrega/gera amostras negativas
    neg_path = Path(NEGATIVE_PATH)
    if not neg_path.exists():
        neg_path.mkdir(parents=True)
        generate_negative_samples(neg_path, 200)
    
    negative_images = list(neg_path.glob("*.jpg"))
    logger.info(f"Encontradas {len(negative_images)} amostras negativas")
    
    # Shuffle e split
    np.random.shuffle(wound_images)
    np.random.shuffle(negative_images)
    
    split_w = int(len(wound_images) * 0.8)
    split_n = int(len(negative_images) * 0.8)
    
    # Copia imagens (redimensionando)
    def copy_images(images, dest_dir, label):
        for i, img_path in enumerate(images):
            try:
                img = cv2.imread(str(img_path))
                if img is None:
                    continue
                img = cv2.resize(img, INPUT_SIZE)
                out_path = dest_dir / label / f"{label}_{i:04d}.jpg"
                cv2.imwrite(str(out_path), img)
            except Exception as e:
                logger.warning(f"Erro: {e}")
    
    logger.info("Copiando imagens de treino...")
    copy_images(wound_images[:split_w], train_dir, "wound")
    copy_images(negative_images[:split_n], train_dir, "no_wound")
    
    logger.info("Copiando imagens de validacao...")
    copy_images(wound_images[split_w:], val_dir, "wound")
    copy_images(negative_images[split_n:], val_dir, "no_wound")
    
    train_count = len(list((train_dir / "wound").glob("*"))) + len(list((train_dir / "no_wound").glob("*")))
    val_count = len(list((val_dir / "wound").glob("*"))) + len(list((val_dir / "no_wound").glob("*")))
    
    logger.info(f"Dataset: {train_count} train, {val_count} val")
    
    return str(train_dir), str(val_dir)


def generate_negative_samples(output_dir: Path, count: int):
    """Gera amostras negativas simples"""
    logger.info(f"Gerando {count} amostras negativas...")
    
    for i in range(count):
        h, w = 224, 224
        
        if i % 3 == 0:
            # Pele saudavel
            skin_tone = np.random.choice([[180, 140, 120], [150, 110, 90], [100, 70, 50]])
            img = np.ones((h, w, 3), dtype=np.uint8) * skin_tone
            noise = np.random.randn(h, w, 3) * 10
            img = np.clip(img + noise, 0, 255).astype(np.uint8)
            img = cv2.GaussianBlur(img, (5, 5), 0)
        elif i % 3 == 1:
            # Dedo
            img = np.ones((h, w, 3), dtype=np.uint8) * 200
            skin = np.random.choice([[180, 140, 120], [150, 110, 90]])
            cv2.ellipse(img, (112, 112), (40, 90), 0, 0, 360, skin, -1)
            img = cv2.GaussianBlur(img, (5, 5), 0)
        else:
            # Dispositivo
            img = np.ones((h, w, 3), dtype=np.uint8) * 200
            cv2.rectangle(img, (20, 20), (200, 200), [40, 40, 40], -1)
            cv2.rectangle(img, (20, 20), (200, 200), [100, 100, 100], 2)
        
        cv2.imwrite(str(output_dir / f"neg_{i:04d}.jpg"), img)


def build_model():
    """Constroi modelo MobileNetV2"""
    base = MobileNetV2(weights='imagenet', include_top=False, input_shape=(*INPUT_SIZE, 3))
    base.trainable = False
    
    inputs = keras.Input(shape=(*INPUT_SIZE, 3))
    x = base(inputs, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(128, activation='relu')(x)
    x = layers.Dropout(0.3)(x)
    outputs = layers.Dense(2, activation='softmax')(x)
    
    model = Model(inputs, outputs)
    model.compile(
        optimizer=keras.optimizers.Adam(LEARNING_RATE),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    
    return model


def train():
    """Executa treinamento"""
    logger.info("=== REDISUS - Treinamento Rapido ===")
    
    # Prepara dataset
    train_dir, val_dir = prepare_dataset()
    
    # Data generators com augmentation online
    train_gen = ImageDataGenerator(
        rescale=1./255,
        rotation_range=20,
        width_shift_range=0.1,
        height_shift_range=0.1,
        horizontal_flip=True,
        zoom_range=0.1,
        brightness_range=[0.8, 1.2]
    )
    
    val_gen = ImageDataGenerator(rescale=1./255)
    
    train_data = train_gen.flow_from_directory(
        train_dir,
        target_size=INPUT_SIZE,
        batch_size=BATCH_SIZE,
        class_mode='categorical'
    )
    
    val_data = val_gen.flow_from_directory(
        val_dir,
        target_size=INPUT_SIZE,
        batch_size=BATCH_SIZE,
        class_mode='categorical'
    )
    
    # Modelo
    logger.info("Construindo modelo MobileNetV2...")
    model = build_model()
    model.summary()
    
    # Output
    output = Path(OUTPUT_PATH)
    output.mkdir(parents=True, exist_ok=True)
    
    # Callbacks
    callbacks = [
        ModelCheckpoint(str(output / "best_model.keras"), save_best_only=True, monitor='val_accuracy'),
        EarlyStopping(patience=5, restore_best_weights=True),
        ReduceLROnPlateau(factor=0.5, patience=3)
    ]
    
    # Class weights
    n_wound = len(list(Path(train_dir).glob("wound/*")))
    n_neg = len(list(Path(train_dir).glob("no_wound/*")))
    total = n_wound + n_neg
    class_weights = {0: total/(2*n_neg), 1: total/(2*n_wound)}
    logger.info(f"Class weights: {class_weights}")
    
    # Treina
    logger.info(f"Iniciando treinamento ({EPOCHS} epochs)...")
    history = model.fit(
        train_data,
        epochs=EPOCHS,
        validation_data=val_data,
        callbacks=callbacks,
        class_weight=class_weights
    )
    
    # Salva modelo final
    model.save(str(output / "wound_detector_final.keras"))
    
    # Salva historico
    with open(output / "history.json", 'w') as f:
        json.dump({k: [float(v) for v in vals] for k, vals in history.history.items()}, f)
    
    logger.info("=== Treinamento Concluido ===")
    logger.info(f"Modelo salvo em: {output}")
    
    # Avaliacao final
    val_loss, val_acc = model.evaluate(val_data)
    logger.info(f"Validacao - Loss: {val_loss:.4f}, Accuracy: {val_acc:.4f}")


if __name__ == "__main__":
    train()
