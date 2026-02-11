"""
REDISUS - Sistema de Diagnóstico de Feridas
Módulo de Exportação e Relatórios

Gera relatórios em diferentes formatos:
- PDF (via reportlab ou fpdf2)
- JSON
- CSV
- Imagem com anotações
"""
import io
import json
import csv
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

import cv2
import numpy as np
from loguru import logger

# PDF generation - tenta reportlab primeiro, depois fpdf2
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm, cm, inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
        Table, TableStyle, PageBreak, HRFlowable
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

try:
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False

PDF_AVAILABLE = HAS_REPORTLAB or HAS_FPDF


@dataclass
class ReportConfig:
    """Configuração do relatório"""
    include_images: bool = True
    include_charts: bool = True
    include_recommendations: bool = True
    include_history: bool = True
    language: str = "pt-BR"
    logo_path: Optional[str] = None


class ExportManager:
    """
    Gerenciador de exportação de dados.
    
    Formatos suportados:
    - JSON: Dados estruturados
    - CSV: Planilha para Excel
    - Imagem: Visualização anotada
    """
    
    def __init__(self, output_dir: str = "output/exports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def export_analysis_json(
        self,
        analysis_data: Dict,
        filename: Optional[str] = None
    ) -> str:
        """
        Exporta análise para JSON.
        
        Args:
            analysis_data: Dados da análise
            filename: Nome do arquivo (auto-gerado se não fornecido)
            
        Returns:
            Caminho do arquivo gerado
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analysis_{timestamp}.json"
            
        filepath = self.output_dir / filename
        
        # Adiciona metadados
        export_data = {
            "export_info": {
                "version": "1.0",
                "exported_at": datetime.now().isoformat(),
                "generator": "REDISUS v1.0"
            },
            "analysis": analysis_data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Análise exportada: {filepath}")
        return str(filepath)
    
    def export_analyses_csv(
        self,
        analyses: List[Dict],
        filename: Optional[str] = None
    ) -> str:
        """
        Exporta múltiplas análises para CSV.
        
        Args:
            analyses: Lista de análises
            filename: Nome do arquivo
            
        Returns:
            Caminho do arquivo
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analyses_{timestamp}.csv"
            
        filepath = self.output_dir / filename
        
        if not analyses:
            logger.warning("Lista de análises vazia")
            return ""
            
        # Define colunas
        columns = [
            "id", "patient_id", "timestamp", "etiology", "confidence",
            "health_score", "wound_area_cm2", "granulation", "slough",
            "necrosis", "epithelialization", "notes"
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            
            for analysis in analyses:
                row = {
                    "id": analysis.get("id", ""),
                    "patient_id": analysis.get("patient_id", ""),
                    "timestamp": analysis.get("timestamp", ""),
                    "etiology": analysis.get("etiology", ""),
                    "confidence": analysis.get("confidence", 0),
                    "health_score": analysis.get("health_score", 0),
                    "wound_area_cm2": analysis.get("wound_area_cm2", ""),
                }
                
                # Extrai porcentagens de tecido
                tissue = analysis.get("tissue_percentages", {})
                row["granulation"] = tissue.get("granulation", 0)
                row["slough"] = tissue.get("slough", 0)
                row["necrosis"] = tissue.get("necrosis", 0)
                row["epithelialization"] = tissue.get("epithelialization", 0)
                row["notes"] = analysis.get("notes", "")
                
                writer.writerow(row)
                
        logger.info(f"Análises exportadas: {filepath}")
        return str(filepath)
    
    def export_annotated_image(
        self,
        image: np.ndarray,
        analysis_data: Dict,
        filename: Optional[str] = None
    ) -> str:
        """
        Exporta imagem com anotações de análise.
        
        Args:
            image: Imagem original
            analysis_data: Dados da análise
            filename: Nome do arquivo
            
        Returns:
            Caminho do arquivo
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"annotated_{timestamp}.jpg"
            
        filepath = self.output_dir / filename
        
        # Cria cópia anotada
        annotated = self._create_annotated_image(image, analysis_data)
        
        cv2.imwrite(str(filepath), annotated)
        
        logger.info(f"Imagem anotada exportada: {filepath}")
        return str(filepath)
    
    def _create_annotated_image(
        self,
        image: np.ndarray,
        analysis_data: Dict
    ) -> np.ndarray:
        """Cria imagem com anotações"""
        h, w = image.shape[:2]
        
        # Cria canvas expandido para informações
        canvas_width = w + 350
        canvas = np.zeros((h, canvas_width, 3), dtype=np.uint8)
        canvas[:] = (40, 40, 40)
        
        # Coloca imagem original
        canvas[:h, :w] = image
        
        # Painel de informações
        x_info = w + 20
        y = 30
        
        # Título
        cv2.putText(canvas, "REDISUS - ANÁLISE", (x_info, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 150), 2)
        y += 35
        
        # Data/hora
        timestamp = analysis_data.get("timestamp", datetime.now().isoformat())
        cv2.putText(canvas, f"Data: {timestamp[:16]}", (x_info, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
        y += 30
        
        # Linha separadora
        cv2.line(canvas, (x_info, y), (canvas_width - 20, y), (80, 80, 80), 1)
        y += 20
        
        # Etiologia
        etiology = analysis_data.get("etiology", "N/A")
        confidence = analysis_data.get("confidence", 0)
        
        cv2.putText(canvas, "Etiologia:", (x_info, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)
        y += 22
        cv2.putText(canvas, etiology, (x_info, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        y += 25
        cv2.putText(canvas, f"Confiança: {confidence:.1%}", (x_info, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
        y += 30
        
        # Health score
        health_score = analysis_data.get("health_score", 0)
        cv2.putText(canvas, f"Score de Saúde: {health_score:.0f}/100", (x_info, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 150), 1)
        y += 30
        
        # Linha separadora
        cv2.line(canvas, (x_info, y), (canvas_width - 20, y), (80, 80, 80), 1)
        y += 20
        
        # Tecidos
        cv2.putText(canvas, "Composição Tecidual:", (x_info, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)
        y += 25
        
        tissues = analysis_data.get("tissue_percentages", {})
        colors = {
            "granulation": (60, 60, 220),
            "slough": (80, 220, 220),
            "necrosis": (50, 50, 50),
            "epithelialization": (200, 180, 255)
        }
        
        for tissue, percentage in sorted(tissues.items(), key=lambda x: -x[1]):
            if percentage > 0.5:
                color = colors.get(tissue, (150, 150, 150))
                cv2.rectangle(canvas, (x_info, y - 10), (x_info + 15, y + 5), color, -1)
                cv2.putText(canvas, f"{tissue}: {percentage:.1f}%", (x_info + 25, y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
                y += 20
                
        # Área
        area = analysis_data.get("wound_area_cm2")
        if area:
            y += 10
            cv2.putText(canvas, f"Área: {area:.2f} cm²", (x_info, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            y += 30
            
        # Linha separadora
        cv2.line(canvas, (x_info, y), (canvas_width - 20, y), (80, 80, 80), 1)
        y += 20
        
        # Aviso se precisa revisão
        if analysis_data.get("needs_review", False):
            cv2.putText(canvas, "⚠ Requer revisão", (x_info, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
            
        return canvas


class ReportGenerator:
    """
    Gerador de relatórios completos.
    
    Gera relatórios formatados com:
    - Resumo da análise
    - Imagens anotadas
    - Histórico de evolução
    - Recomendações de tratamento
    """
    
    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or ReportConfig()
        self.export_manager = ExportManager()
        
    def generate_analysis_report(
        self,
        analysis_data: Dict,
        image: Optional[np.ndarray] = None,
        output_dir: str = "output/reports"
    ) -> Dict[str, str]:
        """
        Gera relatório completo de análise.
        
        Args:
            analysis_data: Dados da análise
            image: Imagem (opcional)
            output_dir: Diretório de saída
            
        Returns:
            Dict com caminhos dos arquivos gerados
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        patient_id = analysis_data.get("patient_id", "unknown")
        base_name = f"report_{patient_id}_{timestamp}"
        
        generated_files = {}
        
        # JSON
        json_path = output_path / f"{base_name}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            report_data = self._create_report_data(analysis_data)
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        generated_files["json"] = str(json_path)
        
        # Imagem anotada
        if image is not None and self.config.include_images:
            img_path = output_path / f"{base_name}.jpg"
            annotated = self.export_manager._create_annotated_image(image, analysis_data)
            cv2.imwrite(str(img_path), annotated)
            generated_files["image"] = str(img_path)
            
        # Texto formatado
        txt_path = output_path / f"{base_name}.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(self._create_text_report(analysis_data))
        generated_files["text"] = str(txt_path)
        
        logger.info(f"Relatório gerado: {output_path / base_name}")
        return generated_files
    
    def _create_report_data(self, analysis_data: Dict) -> Dict:
        """Cria estrutura de dados do relatório"""
        return {
            "report": {
                "title": "Relatório de Análise de Ferida",
                "generated_at": datetime.now().isoformat(),
                "version": "1.0",
                "generator": "REDISUS - Sistema de Diagnóstico de Feridas"
            },
            "patient": {
                "id": analysis_data.get("patient_id", "N/A"),
                "name": analysis_data.get("patient_name", "N/A")
            },
            "analysis": {
                "id": analysis_data.get("id", ""),
                "timestamp": analysis_data.get("timestamp", ""),
                "etiology": {
                    "type": analysis_data.get("etiology", "unknown"),
                    "confidence": analysis_data.get("confidence", 0),
                    "needs_review": analysis_data.get("needs_review", False)
                },
                "tissue_composition": analysis_data.get("tissue_percentages", {}),
                "measurements": {
                    "area_cm2": analysis_data.get("wound_area_cm2"),
                    "health_score": analysis_data.get("health_score", 0)
                }
            },
            "recommendations": analysis_data.get("recommendations", []),
            "notes": analysis_data.get("notes", "")
        }
    
    def _create_text_report(self, analysis_data: Dict) -> str:
        """Cria relatório em texto formatado"""
        lines = [
            "=" * 60,
            "REDISUS - RELATÓRIO DE ANÁLISE DE FERIDA",
            "=" * 60,
            "",
            f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            f"ID da Análise: {analysis_data.get('id', 'N/A')}",
            f"Paciente: {analysis_data.get('patient_id', 'N/A')}",
            "",
            "-" * 60,
            "DIAGNÓSTICO",
            "-" * 60,
            "",
            f"Etiologia: {analysis_data.get('etiology', 'Não identificado')}",
            f"Confiança: {analysis_data.get('confidence', 0):.1%}",
            f"Score de Saúde: {analysis_data.get('health_score', 0):.0f}/100",
            "",
        ]
        
        # Área
        area = analysis_data.get("wound_area_cm2")
        if area:
            lines.append(f"Área da Ferida: {area:.2f} cm²")
            lines.append("")
            
        # Composição tecidual
        lines.extend([
            "-" * 60,
            "COMPOSIÇÃO TECIDUAL",
            "-" * 60,
            ""
        ])
        
        tissues = analysis_data.get("tissue_percentages", {})
        for tissue, percentage in sorted(tissues.items(), key=lambda x: -x[1]):
            if percentage > 0.5:
                bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
                lines.append(f"  {tissue:20} [{bar}] {percentage:.1f}%")
                
        lines.append("")
        
        # Recomendações
        recommendations = analysis_data.get("recommendations", [])
        if recommendations and self.config.include_recommendations:
            lines.extend([
                "-" * 60,
                "RECOMENDAÇÕES",
                "-" * 60,
                ""
            ])
            for i, rec in enumerate(recommendations, 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")
            
        # Notas
        notes = analysis_data.get("notes", "")
        if notes:
            lines.extend([
                "-" * 60,
                "OBSERVAÇÕES",
                "-" * 60,
                "",
                f"  {notes}",
                ""
            ])
            
        # Aviso
        if analysis_data.get("needs_review", False):
            lines.extend([
                "",
                "⚠ ATENÇÃO: Esta análise requer revisão por especialista.",
                ""
            ])
            
        lines.extend([
            "=" * 60,
            "Relatório gerado automaticamente pelo REDISUS",
            "Este documento não substitui avaliação profissional",
            "=" * 60
        ])
        
        return "\n".join(lines)
    
    def generate_evolution_report(
        self,
        analyses: List[Dict],
        patient_info: Dict,
        output_dir: str = "output/reports"
    ) -> str:
        """
        Gera relatório de evolução do paciente.
        
        Args:
            analyses: Lista de análises ordenadas por data
            patient_info: Informações do paciente
            output_dir: Diretório de saída
            
        Returns:
            Caminho do arquivo gerado
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        patient_id = patient_info.get("id", "unknown")
        filepath = output_path / f"evolution_{patient_id}_{timestamp}.txt"
        
        lines = [
            "=" * 70,
            "REDISUS - RELATÓRIO DE EVOLUÇÃO",
            "=" * 70,
            "",
            f"Paciente: {patient_info.get('name', 'N/A')}",
            f"ID: {patient_info.get('id', 'N/A')}",
            f"Período: {analyses[-1].get('timestamp', '')[:10]} a {analyses[0].get('timestamp', '')[:10]}",
            f"Total de Análises: {len(analyses)}",
            "",
            "-" * 70,
            "HISTÓRICO DE ANÁLISES",
            "-" * 70,
            ""
        ]
        
        for i, analysis in enumerate(analyses):
            lines.extend([
                f"Análise #{len(analyses) - i}",
                f"  Data: {analysis.get('timestamp', '')[:16]}",
                f"  Etiologia: {analysis.get('etiology', 'N/A')}",
                f"  Health Score: {analysis.get('health_score', 0):.0f}/100",
                ""
            ])
            
        # Comparação início vs fim
        if len(analyses) >= 2:
            first = analyses[-1]
            last = analyses[0]
            
            score_change = last.get("health_score", 0) - first.get("health_score", 0)
            
            lines.extend([
                "-" * 70,
                "COMPARATIVO",
                "-" * 70,
                "",
                f"Health Score Inicial: {first.get('health_score', 0):.0f}",
                f"Health Score Atual: {last.get('health_score', 0):.0f}",
                f"Variação: {'+' if score_change >= 0 else ''}{score_change:.0f}",
                ""
            ])
            
            if score_change > 10:
                lines.append("✓ EVOLUÇÃO POSITIVA: Melhora significativa observada")
            elif score_change > 0:
                lines.append("→ Leve melhora observada")
            elif score_change > -10:
                lines.append("→ Condição estável")
            else:
                lines.append("⚠ ATENÇÃO: Piora observada, avaliar intervenções")
                
        lines.extend([
            "",
            "=" * 70,
            "Relatório gerado pelo REDISUS",
            "=" * 70
        ])
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
            
        logger.info(f"Relatório de evolução gerado: {filepath}")
        return str(filepath)


class PDFReportGenerator:
    """
    Gerador de relatórios PDF para uso hospitalar.
    
    Gera laudos clínicos completos com:
    - Cabeçalho institucional
    - Dados do paciente
    - Imagens da ferida (original e anotada)
    - Diagnóstico com etiologia e confiança
    - Composição tecidual (gráfico ou tabela)
    - Recomendações de tratamento
    - Assinatura e rodapé legal
    
    Usa reportlab (preferido) ou fpdf2 como fallback.
    """
    
    # Cores padrão
    COLORS = {
        "primary": (0, 102, 153),        # Azul institucional
        "secondary": (51, 51, 51),        # Cinza escuro
        "accent": (0, 153, 102),          # Verde (bom)
        "warning": (255, 153, 0),         # Laranja (atenção)
        "danger": (204, 0, 0),            # Vermelho (alerta)
        "granulation": (220, 60, 60),     # Vermelho
        "slough": (220, 220, 80),         # Amarelo
        "necrosis": (50, 50, 50),         # Preto
        "epithelialization": (255, 180, 200),  # Rosa
        "periwound": (100, 200, 100),     # Verde
    }
    
    def __init__(
        self,
        config: Optional[ReportConfig] = None,
        institution_name: str = "REDISUS - Sistema de Diagnóstico de Feridas",
        institution_logo: Optional[str] = None
    ):
        self.config = config or ReportConfig()
        self.institution_name = institution_name
        self.institution_logo = institution_logo
        
        if not PDF_AVAILABLE:
            logger.warning(
                "Nenhuma biblioteca PDF disponível. "
                "Instale com: pip install reportlab ou pip install fpdf2"
            )
    
    def generate_clinical_report(
        self,
        analysis_data: Dict,
        image: Optional[np.ndarray] = None,
        segmentation_mask: Optional[np.ndarray] = None,
        patient_info: Optional[Dict] = None,
        output_path: Optional[str] = None
    ) -> str:
        """
        Gera relatório PDF clínico completo.
        
        Args:
            analysis_data: Dados da análise (etiologia, tecidos, etc.)
            image: Imagem original da ferida
            segmentation_mask: Máscara de segmentação (opcional)
            patient_info: Informações do paciente
            output_path: Caminho de saída (auto-gerado se não fornecido)
            
        Returns:
            Caminho do arquivo PDF gerado
        """
        if not PDF_AVAILABLE:
            raise ImportError(
                "Biblioteca PDF não disponível. "
                "Instale: pip install reportlab"
            )
        
        # Define caminho de saída
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            patient_id = (patient_info or {}).get("id", "unknown")
            output_dir = Path("output/reports")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / f"laudo_{patient_id}_{timestamp}.pdf")
        
        if HAS_REPORTLAB:
            return self._generate_with_reportlab(
                analysis_data, image, segmentation_mask, 
                patient_info, output_path
            )
        else:
            return self._generate_with_fpdf(
                analysis_data, image, segmentation_mask,
                patient_info, output_path
            )
    
    def _generate_with_reportlab(
        self,
        analysis_data: Dict,
        image: Optional[np.ndarray],
        segmentation_mask: Optional[np.ndarray],
        patient_info: Optional[Dict],
        output_path: str
    ) -> str:
        """Gera PDF usando reportlab"""
        
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # Estilos
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#006699'),
            alignment=TA_CENTER,
            spaceAfter=12
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#333333'),
            spaceBefore=12,
            spaceAfter=6
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#333333'),
            alignment=TA_JUSTIFY
        )
        
        # Elementos do documento
        elements = []
        
        # Cabeçalho
        elements.append(Paragraph(self.institution_name, title_style))
        elements.append(Paragraph("Laudo de Análise de Ferida", styles['Heading2']))
        elements.append(Spacer(1, 0.5*cm))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#006699')))
        elements.append(Spacer(1, 0.3*cm))
        
        # Data e ID
        timestamp = analysis_data.get("timestamp", datetime.now().isoformat())
        analysis_id = analysis_data.get("id", "N/A")
        
        meta_data = [
            ["Data/Hora:", timestamp[:19].replace("T", " ")],
            ["ID da Análise:", analysis_id],
        ]
        
        meta_table = Table(meta_data, colWidths=[4*cm, 10*cm])
        meta_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 0.5*cm))
        
        # Dados do paciente
        if patient_info:
            elements.append(Paragraph("Dados do Paciente", heading_style))
            patient_data = [
                ["Nome:", patient_info.get("name", "N/A")],
                ["ID/Prontuário:", patient_info.get("id", "N/A")],
                ["Idade:", str(patient_info.get("age", "N/A"))],
                ["Leito:", patient_info.get("bed", "N/A")],
            ]
            
            patient_table = Table(patient_data, colWidths=[4*cm, 10*cm])
            patient_table.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8F8F8')),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(patient_table)
            elements.append(Spacer(1, 0.5*cm))
        
        # Imagem da ferida
        if image is not None:
            elements.append(Paragraph("Imagem da Ferida", heading_style))
            
            # Converte imagem para bytes
            img_bytes = self._image_to_bytes(image)
            if img_bytes:
                img = RLImage(img_bytes)
                # Redimensiona mantendo proporção
                max_width = 12*cm
                max_height = 8*cm
                img._restrictSize(max_width, max_height)
                elements.append(img)
                elements.append(Spacer(1, 0.3*cm))
        
        # Diagnóstico
        elements.append(Paragraph("Diagnóstico", heading_style))
        
        etiology = analysis_data.get("etiology", "Não identificado")
        confidence = analysis_data.get("confidence", 0)
        health_score = analysis_data.get("health_score", 0)
        needs_review = analysis_data.get("needs_review", False)
        
        # Determina cores baseadas nos valores
        conf_color = '#009966' if confidence >= 0.7 else '#FF9900' if confidence >= 0.5 else '#CC0000'
        score_color = '#009966' if health_score >= 70 else '#FF9900' if health_score >= 40 else '#CC0000'
        
        diag_html = f"""
        <b>Etiologia:</b> {etiology}<br/>
        <b>Confiança:</b> <font color="{conf_color}">{confidence:.1%}</font><br/>
        <b>Score de Saúde:</b> <font color="{score_color}">{health_score:.0f}/100</font>
        """
        elements.append(Paragraph(diag_html, body_style))
        
        if needs_review:
            warning_style = ParagraphStyle(
                'Warning',
                parent=body_style,
                textColor=colors.HexColor('#CC0000'),
                fontSize=10,
                spaceBefore=6
            )
            elements.append(Paragraph(
                "⚠ Esta análise requer revisão por especialista", 
                warning_style
            ))
        
        # Área da ferida
        area = analysis_data.get("wound_area_cm2")
        if area:
            elements.append(Paragraph(f"<b>Área estimada:</b> {area:.2f} cm²", body_style))
        
        elements.append(Spacer(1, 0.5*cm))
        
        # Composição tecidual
        tissues = analysis_data.get("tissue_percentages", {})
        if tissues:
            elements.append(Paragraph("Composição Tecidual", heading_style))
            
            tissue_names = {
                "granulation": "Granulação",
                "slough": "Esfacelo",
                "necrosis": "Necrose",
                "epithelialization": "Epitelização",
                "periwound": "Pele Perilesional"
            }
            
            tissue_colors = {
                "granulation": colors.HexColor('#DC3C3C'),
                "slough": colors.HexColor('#DCDC50'),
                "necrosis": colors.HexColor('#323232'),
                "epithelialization": colors.HexColor('#FFB4C8'),
                "periwound": colors.HexColor('#64C864')
            }
            
            tissue_data = [["Tecido", "Porcentagem", "Barra"]]
            
            for tissue, percentage in sorted(tissues.items(), key=lambda x: -x[1]):
                if percentage > 0.5:
                    name = tissue_names.get(tissue, tissue.capitalize())
                    bar = "█" * int(percentage / 5)
                    tissue_data.append([name, f"{percentage:.1f}%", bar])
            
            if len(tissue_data) > 1:
                tissue_table = Table(tissue_data, colWidths=[4*cm, 3*cm, 7*cm])
                tissue_table.setStyle(TableStyle([
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#006699')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F0')]),
                    ('PADDING', (0, 0), (-1, -1), 6),
                ]))
                elements.append(tissue_table)
                elements.append(Spacer(1, 0.5*cm))
        
        # Recomendações
        recommendations = analysis_data.get("recommendations", [])
        if recommendations and self.config.include_recommendations:
            elements.append(Paragraph("Recomendações de Tratamento", heading_style))
            
            rec_text = "<br/>".join([f"• {rec}" for rec in recommendations])
            elements.append(Paragraph(rec_text, body_style))
            elements.append(Spacer(1, 0.5*cm))
        
        # Observações
        notes = analysis_data.get("notes", "")
        if notes:
            elements.append(Paragraph("Observações", heading_style))
            elements.append(Paragraph(notes, body_style))
            elements.append(Spacer(1, 0.5*cm))
        
        # Rodapé legal
        elements.append(Spacer(1, 1*cm))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CCCCCC')))
        
        footer_style = ParagraphStyle(
            'Footer',
            parent=body_style,
            fontSize=8,
            textColor=colors.HexColor('#999999'),
            alignment=TA_CENTER
        )
        
        elements.append(Paragraph(
            "Relatório gerado automaticamente pelo REDISUS - Sistema de Diagnóstico de Feridas<br/>"
            "Este documento é um auxílio diagnóstico e não substitui a avaliação clínica profissional.<br/>"
            f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            footer_style
        ))
        
        # Assinatura
        elements.append(Spacer(1, 1.5*cm))
        
        sig_data = [
            ["_" * 40],
            ["Assinatura do Profissional"],
            ["CRM/COREN: _______________"]
        ]
        sig_table = Table(sig_data, colWidths=[8*cm])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#666666')),
        ]))
        elements.append(sig_table)
        
        # Gera PDF
        doc.build(elements)
        
        logger.info(f"Relatório PDF gerado: {output_path}")
        return output_path
    
    def _generate_with_fpdf(
        self,
        analysis_data: Dict,
        image: Optional[np.ndarray],
        segmentation_mask: Optional[np.ndarray],
        patient_info: Optional[Dict],
        output_path: str
    ) -> str:
        """Gera PDF usando fpdf2 (fallback)"""
        
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        # Título
        pdf.set_font('Helvetica', 'B', 18)
        pdf.set_text_color(0, 102, 153)
        pdf.cell(0, 10, self.institution_name, ln=True, align='C')
        
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(51, 51, 51)
        pdf.cell(0, 8, 'Laudo de Analise de Ferida', ln=True, align='C')
        
        pdf.ln(5)
        pdf.set_draw_color(0, 102, 153)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(10)
        
        # Metadata
        pdf.set_font('Helvetica', '', 10)
        timestamp = analysis_data.get("timestamp", datetime.now().isoformat())
        pdf.cell(0, 6, f'Data/Hora: {timestamp[:19]}', ln=True)
        pdf.cell(0, 6, f'ID: {analysis_data.get("id", "N/A")}', ln=True)
        pdf.ln(5)
        
        # Paciente
        if patient_info:
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(0, 8, 'Dados do Paciente', ln=True)
            pdf.set_font('Helvetica', '', 10)
            pdf.cell(0, 6, f'Nome: {patient_info.get("name", "N/A")}', ln=True)
            pdf.cell(0, 6, f'ID: {patient_info.get("id", "N/A")}', ln=True)
            pdf.ln(5)
        
        # Imagem
        if image is not None:
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(0, 8, 'Imagem da Ferida', ln=True)
            
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
                cv2.imwrite(f.name, image)
                pdf.image(f.name, x=20, w=80)
            pdf.ln(5)
        
        # Diagnóstico
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Diagnostico', ln=True)
        pdf.set_font('Helvetica', '', 10)
        
        etiology = analysis_data.get("etiology", "Nao identificado")
        confidence = analysis_data.get("confidence", 0)
        health_score = analysis_data.get("health_score", 0)
        
        pdf.cell(0, 6, f'Etiologia: {etiology}', ln=True)
        pdf.cell(0, 6, f'Confianca: {confidence:.1%}', ln=True)
        pdf.cell(0, 6, f'Score de Saude: {health_score:.0f}/100', ln=True)
        
        area = analysis_data.get("wound_area_cm2")
        if area:
            pdf.cell(0, 6, f'Area: {area:.2f} cm2', ln=True)
        pdf.ln(5)
        
        # Tecidos
        tissues = analysis_data.get("tissue_percentages", {})
        if tissues:
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(0, 8, 'Composicao Tecidual', ln=True)
            pdf.set_font('Helvetica', '', 10)
            
            tissue_names = {
                "granulation": "Granulacao",
                "slough": "Esfacelo",
                "necrosis": "Necrose",
                "epithelialization": "Epitelizacao"
            }
            
            for tissue, percentage in sorted(tissues.items(), key=lambda x: -x[1]):
                if percentage > 0.5:
                    name = tissue_names.get(tissue, tissue)
                    bar = chr(9608) * int(percentage / 5)
                    pdf.cell(0, 5, f'{name}: {percentage:.1f}% {bar}', ln=True)
            pdf.ln(5)
        
        # Recomendações
        recommendations = analysis_data.get("recommendations", [])
        if recommendations:
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(0, 8, 'Recomendacoes', ln=True)
            pdf.set_font('Helvetica', '', 10)
            for rec in recommendations:
                pdf.multi_cell(0, 5, f'- {rec}')
            pdf.ln(5)
        
        # Rodapé
        pdf.ln(10)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(5)
        
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(150, 150, 150)
        pdf.multi_cell(
            0, 4,
            'Relatorio gerado automaticamente pelo REDISUS.\n'
            'Este documento nao substitui a avaliacao clinica profissional.',
            align='C'
        )
        
        # Assinatura
        pdf.ln(15)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, '_' * 40, ln=True, align='C')
        pdf.cell(0, 5, 'Assinatura do Profissional', ln=True, align='C')
        
        # Salva
        pdf.output(output_path)
        
        logger.info(f"Relatório PDF gerado: {output_path}")
        return output_path
    
    def _image_to_bytes(self, image: np.ndarray) -> Optional[io.BytesIO]:
        """Converte imagem numpy para BytesIO para uso no reportlab"""
        try:
            # Converte BGR para RGB se necessário
            if len(image.shape) == 3 and image.shape[2] == 3:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = image
            
            # Codifica como JPEG
            success, buffer = cv2.imencode('.jpg', image_rgb, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if success:
                return io.BytesIO(buffer.tobytes())
            return None
        except Exception as e:
            logger.warning(f"Erro ao converter imagem: {e}")
            return None
    
    def generate_evolution_report_pdf(
        self,
        analyses: List[Dict],
        patient_info: Dict,
        images: Optional[List[np.ndarray]] = None,
        output_path: Optional[str] = None
    ) -> str:
        """
        Gera relatório PDF de evolução do paciente.
        
        Args:
            analyses: Lista de análises ordenadas por data
            patient_info: Informações do paciente
            images: Lista de imagens correspondentes (opcional)
            output_path: Caminho de saída
            
        Returns:
            Caminho do arquivo PDF
        """
        if not PDF_AVAILABLE:
            raise ImportError("Biblioteca PDF não disponível")
        
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            patient_id = patient_info.get("id", "unknown")
            output_dir = Path("output/reports")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / f"evolucao_{patient_id}_{timestamp}.pdf")
        
        if not HAS_REPORTLAB:
            logger.warning("reportlab não disponível, usando fpdf2")
            # Implementação simplificada com fpdf2
            return self._generate_evolution_fpdf(analyses, patient_info, output_path)
        
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        styles = getSampleStyleSheet()
        elements = []
        
        # Título
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#006699'),
            alignment=TA_CENTER
        )
        
        elements.append(Paragraph(self.institution_name, title_style))
        elements.append(Paragraph("Relatório de Evolução", styles['Heading2']))
        elements.append(Spacer(1, 0.5*cm))
        
        # Dados do paciente
        elements.append(Paragraph(
            f"<b>Paciente:</b> {patient_info.get('name', 'N/A')}<br/>"
            f"<b>ID:</b> {patient_info.get('id', 'N/A')}<br/>"
            f"<b>Período:</b> {len(analyses)} análises",
            styles['Normal']
        ))
        elements.append(Spacer(1, 0.5*cm))
        
        # Tabela de evolução
        if analyses:
            elements.append(Paragraph("Histórico de Análises", styles['Heading2']))
            
            table_data = [["Data", "Etiologia", "Score", "Confiança"]]
            
            for analysis in analyses:
                table_data.append([
                    analysis.get("timestamp", "")[:10],
                    analysis.get("etiology", "N/A")[:20],
                    f"{analysis.get('health_score', 0):.0f}",
                    f"{analysis.get('confidence', 0):.0%}"
                ])
            
            table = Table(table_data, colWidths=[3*cm, 6*cm, 2.5*cm, 2.5*cm])
            table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#006699')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.5*cm))
            
            # Comparativo
            if len(analyses) >= 2:
                first = analyses[-1]
                last = analyses[0]
                score_change = last.get("health_score", 0) - first.get("health_score", 0)
                
                elements.append(Paragraph("Comparativo", styles['Heading2']))
                
                trend = "↑ Melhora" if score_change > 5 else "↓ Piora" if score_change < -5 else "→ Estável"
                trend_color = '#009966' if score_change > 5 else '#CC0000' if score_change < -5 else '#666666'
                
                comp_text = f"""
                <b>Score Inicial:</b> {first.get('health_score', 0):.0f}/100<br/>
                <b>Score Atual:</b> {last.get('health_score', 0):.0f}/100<br/>
                <b>Variação:</b> <font color="{trend_color}">{'+' if score_change > 0 else ''}{score_change:.0f} ({trend})</font>
                """
                elements.append(Paragraph(comp_text, styles['Normal']))
        
        # Rodapé
        elements.append(Spacer(1, 1*cm))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#999999'),
            alignment=TA_CENTER
        )
        elements.append(Paragraph(
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} pelo REDISUS",
            footer_style
        ))
        
        doc.build(elements)
        logger.info(f"Relatório de evolução PDF gerado: {output_path}")
        return output_path
    
    def _generate_evolution_fpdf(
        self,
        analyses: List[Dict],
        patient_info: Dict,
        output_path: str
    ) -> str:
        """Gera relatório de evolução com fpdf2"""
        pdf = FPDF()
        pdf.add_page()
        
        pdf.set_font('Helvetica', 'B', 16)
        pdf.cell(0, 10, 'Relatorio de Evolucao', ln=True, align='C')
        pdf.ln(10)
        
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, f'Paciente: {patient_info.get("name", "N/A")}', ln=True)
        pdf.cell(0, 6, f'ID: {patient_info.get("id", "N/A")}', ln=True)
        pdf.ln(10)
        
        for i, analysis in enumerate(analyses):
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(0, 6, f'Analise {i+1}: {analysis.get("timestamp", "")[:10]}', ln=True)
            pdf.set_font('Helvetica', '', 10)
            pdf.cell(0, 5, f'  Score: {analysis.get("health_score", 0):.0f}/100', ln=True)
            pdf.cell(0, 5, f'  Etiologia: {analysis.get("etiology", "N/A")}', ln=True)
            pdf.ln(3)
        
        pdf.output(output_path)
        return output_path
