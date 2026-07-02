"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useTheme } from "../../app/providers/ThemeProvider";
import { Sun, Moon } from "lucide-react";

const translations = {
  pt: {
    plataforma: "Plataforma",
    fluxo: "Fluxo",
    tecnologia: "Tecnologia",
    instituicoes: "Instituições",
    entrar: "Entrar",
    acessar: "Acessar",
    badgeText: "Fundamentação e Tecnologia",
    refTitle: "Referências do Trabalho",
    refSubtitle: "Base teórica, protocolos clínicos e arquitetura tecnológica completa que estruturam a plataforma HEAL+.",
    techTitle: "Stack Tecnológico e IA",
    techDesc1: "Frontend (Web Portal)",
    techText1: "Desenvolvido em Next.js 14, React 18 e Tailwind CSS, oferecendo uma experiência moderna com App Router e design adaptativo (Light/Dark mode).",
    techDesc2: "Backend & Infraestrutura",
    techText2: "Arquitetura sustentada por Python (Flask API), banco de dados relacional (Supabase Postgres) e Storage na nuvem do Supabase.",
    techDesc3: "Modelos de Visão Computacional",
    techText3: "Implementação de algoritmos de Deep Learning e Visão Computacional (OpenCV, YOLOv8 e ResNet50) para avaliação tecidual clínica.",
    techDesc4: "Inteligência Artificial (LLM)",
    techText4: "Uso avançado de IA Generativa (Google Gemini 2.0 Flash) processando análise multimodal (dados e texto) integrado como agente de apoio à decisão.",
    openTitle: "Ferramentas e Arquiteturas Open-Source",
    bibTitle: "Bibliografia Científica",
    docLink: "Ver documento",
    toastPt: "Idioma: Português (BR)",
    toastEn: "Language: English (US)",
    footerText: "© {year} HEAL+ REDISUS."
  },
  en: {
    plataforma: "Platform",
    fluxo: "Flow",
    tecnologia: "Technology",
    instituicoes: "Institutions",
    entrar: "Sign In",
    acessar: "Access",
    badgeText: "Foundation & Technology",
    refTitle: "Project References",
    refSubtitle: "Theoretical framework, clinical protocols, and complete technological architecture underlying the HEAL+ platform.",
    techTitle: "Tech Stack & AI",
    techDesc1: "Frontend (Web Portal)",
    techText1: "Developed in Next.js 14, React 18, and Tailwind CSS, offering a modern experience with App Router and adaptive design (Light/Dark mode).",
    techDesc2: "Backend & Infrastructure",
    techText2: "Architecture supported by Python (Flask API), relational database (Supabase Postgres), and Supabase cloud Storage.",
    techDesc3: "Computer Vision Models",
    techText3: "Implementation of Deep Learning and Computer Vision algorithms (OpenCV, YOLOv8, and ResNet50) for clinical tissue evaluation.",
    techDesc4: "Artificial Intelligence (LLM)",
    techText4: "Advanced use of Generative AI (Google Gemini 2.0 Flash) processing multimodal data and text, integrated as a decision-support agent.",
    openTitle: "Open-Source Tools & Architectures",
    bibTitle: "Scientific Bibliography",
    docLink: "View document",
    toastPt: "Idioma: Português (BR)",
    toastEn: "Language: English (US)",
    footerText: "© {year} HEAL+ REDISUS."
  }
};

const references = [
  {
    id: 1,
    text: "ARAÚJO, T. M. et al. Realidade virtual no alívio da dor durante a troca de curativos de feridas crônicas. Revista da Escola de Enfermagem da USP, São Paulo, v. 55, e20200513, 2021. DOI: https://doi.org/10.1590/1980-220X-REEUSP-2020-0513. Disponível em: https://www.scielo.br/j/reeusp/a/xLqsRvkycBVLt3DD7BsM4tP/?lang=pt&format=pdf. Acesso em: 30 maio 2025.",
    link: "https://www.scielo.br/j/reeusp/a/xLqsRvkycBVLt3DD7BsM4tP/?lang=pt&format=pdf"
  },
  {
    id: 2,
    text: "BORGES, Eline Lima; SOUZA, Perla Oliveira Soares de. Feridas: como tratar. 3. ed. Rio de Janeiro: Rubio, 2024. p. 61-88."
  },
  {
    id: 3,
    text: "FLORIANÓPOLIS. Prefeitura Municipal. Secretaria Municipal de Saúde. Protocolo de cuidados de feridas. Florianópolis, SC: SMS, 2008."
  },
  {
    id: 4,
    text: "GERMANO, Renan Soares; ELISEO, Maria Amelia; SILVEIRA, Ismar Frango. Introdução à acessibilidade na Web: do conceito à prática. In: JORNADAS IBERO-AMERICANAS DE INTERAÇÃO HUMANO-COMPUTADOR, 7., 2021, São Paulo. Anais [...]. São Paulo: Sociedade Brasileira de Computação, 2021."
  },
  {
    id: 5,
    text: "LIMA, E. V. M. et al. Construction of a mobile application for wound assessment for nursing students and professionals. Estima – Brazilian Journal of Enterostomal Therapy, [S. l.], v. 22, art. 1515, 2024. Disponível em: https://www.revistaestima.com.br/estima/article/view/1515. Acesso em: 1 nov. 2024.",
    link: "https://www.revistaestima.com.br/estima/article/view/1515"
  },
  {
    id: 6,
    text: "MADRIL MEDEIROS, R. M. et al. Contribuição de um software para o registro, monitoramento e avaliação de feridas. Global Academic Nursing Journal, [S. l.], v. 2, n. 3, p. e146, 2021. DOI: 10.5935/2675-5602.20200146. Disponível em: https://www.globalacademicnursing.com/index.php/globacadnurs/article/view/123. Acesso em: 7 mar. 2025.",
    link: "https://www.globalacademicnursing.com/index.php/globacadnurs/article/view/123"
  },
  {
    id: 7,
    text: "MEDETEC. Medetec Image Databases. A collection of wound images for research and education. Disponível em: https://www.medetec.co.uk/files/medetec-image-databases.html.",
    link: "https://www.medetec.co.uk/files/medetec-image-databases.html"
  },
  {
    id: 8,
    text: "MENOITA, E.; SEARA, A.; SANTOS, V. Plano de Tratamento dirigido aos Sinais Clínicos da Infecção da Ferida. Journal of Aging & Inovation, v. 3, n. 2, p. 62-73, 2014."
  },
  {
    id: 9,
    text: "PAULA, M. A. B.; SANTOS, V. L. C. G. O significado de ser especialista para o enfermeiro estomaterapeuta. Revista Latino-Americana de Enfermagem, Ribeirão Preto, v. 11, n. 4, p. 474–482, jul. 2003. Disponível em: https://www.scielo.br/j/rlae/a/mvBJQ3wFgTGjT6hJ4NNDVxS/. Acesso em: 13 nov. 2024.",
    link: "https://www.scielo.br/j/rlae/a/mvBJQ3wFgTGjT6hJ4NNDVxS/"
  },
  {
    id: 10,
    text: "ROCHA, Adiel Andrade. Feridômetro: aplicativo de auxílio à aprendizagem do acrônimo TIMERS. 2021. Trabalho de Conclusão de Curso (Graduação em Ciência da Computação) – Universidade Federal de Campina Grande, Campina Grande, 2021. Disponível em: https://dspace.sti.ufcg.edu.br/bitstream/riufcg/19691/1/ADIEL%20ANDRADE%20ROCHA%20-%20TCC%20CI%C3%8ANCIA%20DA%20COMPUTA%C3%87%C3%83O%202021.pdf. Acesso em: 2 set. 2025.",
    link: "https://dspace.sti.ufcg.edu.br/bitstream/riufcg/19691/1/ADIEL%20ANDRADE%20ROCHA%20-%20TCC%20CI%C3%8ANCIA%20DA%20COMPUTA%C3%87%C3%83O%202021.pdf"
  },
  {
    id: 11,
    text: "SILVA, Cláudio Xavier da. Sis-MF - Aplicativo para monitoramento da cicatrização de feridas. 2018. Dissertação (Mestrado Profissional em Ciências) – Universidade Federal de São Paulo, São Paulo, 2018."
  },
  {
    id: 12,
    text: "SOARES PACZEK, R. et al. A ESTOMATERAPIA COMO CAMPO DE ESTÁGIO. In: CONGRESSO BRASILEIRO DE ESTOMATERAPIA, [S. l.], 2024. Anais [...]. [S. l.]: SOBEST, 2024. Disponível em: https://anais.sobest.com.br/cbe/article/view/447. Acesso em: 20 out. 2024.",
    link: "https://anais.sobest.com.br/cbe/article/view/447"
  },
  {
    id: 13,
    text: "Sen, C. K., et al. (2009). Human skin wounds: A major and snowballing threat to public health and the economy. *Wound Repair and Regeneration*, 17(6), 763–771."
  },
  {
    id: 14,
    text: "Järbrink, K., et al. (2017). The humanistic and economic burden of chronic wounds: a protocol for a systematic review. *Systematic Reviews*, 6(1), 15."
  },
  {
    id: 15,
    text: "Ma, J., et al. (2024). Segment anything in medical images. *Nature Communications*, 15, 654. *(MedSAM)*"
  },
  {
    id: 16,
    text: "Zhang, Y., et al. (2023). BiomedCLIP: A multimodal biomedical foundation model pretrained from fifteen million scientific image-text pairs. *arXiv:2303.00915*. *(BiomedCLIP)*"
  },
  {
    id: 17,
    text: "Schultz, G. S., et al. (2003). Wound bed preparation: a systematic approach to wound management. *Wound Repair and Regeneration*, 11(S1), S1–S28. *(Abordagem TIME)*"
  },
  {
    id: 18,
    text: "O'Meara, S., et al. (2012). Compression for venous leg ulcers. *Cochrane Database of Systematic Reviews*. *(Compressão multicomponente)*"
  },
  {
    id: 19,
    text: "Bergstrom, N., et al. (1987). The Braden Scale for predicting pressure sore risk. *Nursing Research*, 36(4), 205–210."
  },
  {
    id: 20,
    text: "Wagner, F. W. (1981). The dysvascular foot: a system for diagnosis and treatment. *Foot & Ankle*, 2(2), 64–122. *(Escala de Wagner)*"
  },
  {
    id: 21,
    text: "Anisuzzaman, D. M., et al. (2022). Image-based artificial intelligence in wound assessment: A systematic review. *Advances in Wound Care*, 11(12), 687–709."
  },
  {
    id: 22,
    text: "Ronneberger, O., et al. (2015). U-Net: Convolutional Networks for Biomedical Image Segmentation. *MICCAI*, 234–241."
  },
  {
    id: 23,
    text: "He, K., et al. (2016). Deep Residual Learning for Image Recognition. *CVPR*, 770–778. *(ResNet)*"
  },
  {
    id: 24,
    text: "Redmon, J., et al. (2016–2023). YOLOv1→v8: evolução de detectores de objetos em tempo real. *Ultralytics*. *(YOLOv8)*"
  },
  {
    id: 25,
    text: "Tan, M. & Le, Q. (2019). EfficientNet: Rethinking Model Scaling for Convolutional Neural Networks. *ICML*. *(EfficientNet)*"
  },
  {
    id: 26,
    text: "Wang, C., et al. (2023). Wound Segmentation Network (WSNet). *WACV 2023*. *(Wseg dataset — 2686 imagens)*"
  },
  {
    id: 27,
    text: "Cassidy, B., et al. (2021). The DFUC 2020 dataset: Analysis towards diabetic foot ulcer detection. *BioMedical Engineering OnLine*. *(DFUC Challenge)*"
  },
  {
    id: 28,
    text: "Botelho, S. S. C., et al. (2024). Performance-watt analysis of GPU-based digital twin simulations. In: *IECON 2024 — 50th Annual Conference of the IEEE Industrial Electronics Society* (USA)."
  },
  {
    id: 29,
    text: "Niemiec, W.; Cota, E. (2025). Towards a component-based framework for mHealth apps: Bridging the gap between the nursing domain language and the computation domain. *Journal of Systems and Software*, 230:112497. https://doi.org/10.1016/j.jss.2025.112497 *(TAKERE)*",
    link: "https://doi.org/10.1016/j.jss.2025.112497"
  },
  {
    id: 30,
    text: "Niemiec, W.; Tavares, A. R.; Cota, E. (2025). Leveraging Natural Language Processing for mHealth Development: A Component-Based Approach Using Nursing Taxonomies. *Proc. IEEE CBMS*. doi:10.1109/CBMS65348.2025.00084 *(TAKERE/NLP)*"
  },
  {
    id: 31,
    text: "Oliveira, V. M., et al. (2024). Digital Twin Across Industry 5.0: Integrating Dimensional Analysis to a Rotor Inspection Module. In: *2024 IEEE 22nd Int. Conf. on Industrial Informatics*, Beijing. *(Twin@Home)*"
  },
  {
    id: 32,
    text: "Carvalho, R.; Sampaio, A. F.; Vasconcelos, M. J. M. (2025). Automating Tissue Segmentation and Quantification for Wound Healing Assessment. In: *2025 IEEE 38th CBMS*, Madrid, p. 160–166. doi:10.1109/CBMS65348.2025.00042"
  },
  {
    id: 33,
    text: "Bahadır, E. B.; Sezgintürk, M. K. (2016). Lateral flow assays: principles, designs and labels. *TrAC Trends in Analytical Chemistry*. *(REDE VIVA)*"
  },
  {
    id: 34,
    text: "Pias, M. R., et al. (2025). On the scaling of digital twins by aggregation. *Data & Policy*, 7:e9. *(Twin@Home)*"
  },
  {
    id: 35,
    text: "Gomis-Pastor, M., et al. Improving patients' experience and medication adherence after heart failure treatment: mixed methods study. *(Experiência do Paciente)*"
  },
  {
    id: 36,
    text: "INCA. (2021). *Detecção precoce do câncer*. Rio de Janeiro: INCA. 72 p. ISBN 978-65-88517-22-2. *(DermaSUS)*"
  },
  {
    id: 37,
    text: "Jakob, R., et al. (2022). Factors Influencing Adherence to mHealth Apps for Prevention or Management of Noncommunicable Diseases: Systematic Review. *J Med Internet Res*, 24(5):e35371. doi:10.2196/35371 *(mHealth/Adesão)*"
  },
  {
    id: 38,
    text: "Laubenbacher, R., et al. (2024). Digital twins in medicine. *Nature Computational Science*. *(Twin@Home)*"
  },
  {
    id: 39,
    text: "Liu, Y., et al. (2019). A Novel Cloud-Based Framework for the Elderly Healthcare Services Using Digital Twin. *IEEE Access*. *(Twin@Home)*"
  },
  {
    id: 40,
    text: "Orofino-Costa, R., et al. (2017). Sporotrichosis: an update on epidemiology, etiopathogenesis, laboratory and clinical therapeutics. *An Bras Dermatol*. *(REDE VIVA)*"
  },
  {
    id: 41,
    text: "Sehat Ullah, et al. (2025). Machine Learning and Digital-Twins-Based Internet of Robotic Things for Remote Patient Monitoring. *IEEE Journals & Magazine*. *(Twin@Home/IoT)*"
  },
  {
    id: 42,
    text: "Shamsuddeen, A., et al. (2024). The future of skin cancer diagnosis: a comprehensive systematic review of ML and DL models. *Cogent Engineering*, 11(1):2395425. https://doi.org/10.1080/23311916.2024.2395425 *(DermaSUS)*",
    link: "https://doi.org/10.1080/23311916.2024.2395425"
  },
  {
    id: 43,
    text: "Somfai, E., et al. (2023). Handling dataset dependence with model ensembles for skin lesion classification from dermoscopic and clinical images. *Int J Imaging Syst Technol*, 33(2):556–571. *(Ensemble/DermaSUS)*"
  },
  {
    id: 44,
    text: "Tambella, A. M., et al. (2025). Avanços na medição sem contato da área da ferida usando aplicativo móvel. *Skin Wound Care*, 38(7):360–366. doi:10.1097/ASW.0000000000000296 *(Medição de feridas/mHealth)*"
  },
  {
    id: 45,
    text: "McMahan, B., et al. (2017). Communication-Efficient Learning of Deep Networks from Decentralized Data. *AISTATS*. *(Federated Learning)*"
  },
  {
    id: 46,
    text: "SANCHEZ, Karen et al. CO2Wounds-V2: Extended Chronic Wounds Dataset From Leprosy Patients. In: IEEE International Conference on Image Processing, 2024. DOI: 10.1109/ICIP51287.2024.10647641. Dataset usado no Heal+ apenas para pesquisa, prova de conceito e treinamento experimental de segmentacao ferida vs. fundo, respeitando restricoes nao comerciais.",
    link: "https://github.com/simatec-uis/CO2Wounds-V2"
  },
  {
    id: 47,
    text: "SANCHEZ, Karen et al. CO2Wounds-V2: Extended Chronic Wounds Dataset From Leprosy Patients. Mendeley Data, v. 2, 2024. DOI: 10.17632/s2w7rjwz49.2. Licenca informada: Creative Commons Attribution-NonCommercial 3.0 Unported (CC BY-NC 3.0); uso comercial exige revisao juridica/autorizacao formal.",
    link: "https://data.mendeley.com/datasets/s2w7rjwz49/2"
  }
];

export default function ReferenciasPage() {
  const [lang, setLang] = useState<"pt" | "en">("pt");
  const { theme, toggleTheme } = useTheme();
  const [showToast, setShowToast] = useState(false);
  const [toastMsg, setToastMsg] = useState("");

  const triggerToast = (msg: string) => {
    setToastMsg(msg);
    setShowToast(true);
    setTimeout(() => setShowToast(false), 3000);
  };

  const t = (key: keyof typeof translations.pt) => {
    return translations[lang][key];
  };

  const openSourceTools = [
    { title: "YOLOv8 & Ultralytics", desc: lang === "pt" ? "Detecção de objetos em tempo real em duas vias para identificação estrutural e localização primária da lesão no quadro." : "Real-time object detection in two ways for structural identification and primary lesion localization in the frame." },
    { title: "BiomedCLIP (Microsoft)", desc: lang === "pt" ? "Análise zero-shot multimodal construída com base em linguagem de visão unificada adaptada exclusivamente para o domínio biomédico." : "Multimodal zero-shot analysis built on unified vision-language pre-training adapted exclusively for the biomedical domain." },
    { title: "MedSAM", desc: lang === "pt" ? "Modelo base de IA adaptado da arquitetura genérica SAM (Segment Anything) voltado à segmentação granular de bordas em imagens médicas." : "AI foundation model adapted from the generic SAM (Segment Anything) architecture, aimed at granular boundary segmentation in medical images." },
    { title: "DermaIntel ViT", desc: lang === "pt" ? "Classificador de ferimentos cutâneos baseado em arquitetura moderna de Transformadores Visuais (Vision Transformers - Hugging Face)." : "Skin lesion classifier based on modern Vision Transformers architecture (Vision Transformers - Hugging Face)." },
    { title: "MediaPipe", desc: lang === "pt" ? "Framework rápido para rastreamento holístico e detecção de pontos articulares para enquadramento do paciente acamado." : "Fast framework for holistic tracking and joint point detection to capture the bedridden patient framing." },
    { title: "HL7 FHIR R4", desc: lang === "pt" ? "Conjunto de padrões internacionais de interoperabilidade semântica (em estruturação) para troca de dados de prontuário com o DATASUS." : "A set of international semantic interoperability standards (under structuring) for health record exchange with DATASUS." }
  ];

  return (
    <div className="min-h-screen overflow-x-hidden bg-[#f7faff] text-[#101828] dark:bg-[#050608] dark:text-[#f2f4f7] font-sans antialiased transition-colors duration-300">
      
      {/* ─── HEADER (NAVBAR) ─── */}
      <nav className="fixed left-0 top-0 z-50 w-full border-b border-slate-100 dark:border-slate-900 bg-white/95 dark:bg-[#050608]/95 text-slate-900 dark:text-white shadow-sm backdrop-blur-2xl transition-all duration-300">
        <div className="mx-auto flex h-[76px] w-full max-w-[1530px] items-center justify-between px-5 md:px-8">
          <Link href="/" className="flex min-w-0 items-center gap-3">
            <Image
              src="/images/Logo_final_modobranco.png"
              alt="Heal+"
              width={120}
              height={44}
              className="h-10 w-auto object-contain shrink-0"
            />
          </Link>
          <div className="hidden items-center gap-7 lg:flex">
            <a href="/#plataforma" className="text-sm font-extrabold text-slate-600 dark:text-slate-400 transition-colors hover:text-[#41B6E6]">{t("plataforma")}</a>
            <a href="/#fluxo" className="text-sm font-extrabold text-slate-600 dark:text-slate-400 transition-colors hover:text-[#41B6E6]">{t("fluxo")}</a>
            <a href="/#tecnologia" className="text-sm font-extrabold text-slate-600 dark:text-slate-400 transition-colors hover:text-[#41B6E6]">{t("tecnologia")}</a>
            <a href="/#instituicoes" className="text-sm font-extrabold text-slate-600 dark:text-slate-400 transition-colors hover:text-[#41B6E6]">{t("instituicoes")}</a>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            {/* Language Selector Button */}
            <button
              type="button"
              onClick={() => {
                const nextLang = lang === "pt" ? "en" : "pt";
                setLang(nextLang);
                triggerToast(nextLang === "pt" ? t("toastPt") : t("toastEn"));
              }}
              className="flex items-center gap-1.5 rounded-full border border-slate-250 dark:border-slate-800 bg-transparent px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:border-[#41B6E6] dark:hover:border-[#41B6E6] hover:bg-slate-50 dark:hover:bg-[#1E1E24] transition-all duration-205 cursor-pointer"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
              </svg>
              {lang === "pt" ? "Português" : "English"}
            </button>

            {/* Dark/Light mode toggle switch */}
            <button
              onClick={toggleTheme}
              className="p-2.5 rounded-full hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors text-slate-600 dark:text-slate-350 mr-1 cursor-pointer"
              aria-label="Alternar Tema"
            >
              {theme === "dark" ? <Sun size={20} className="text-[#41B6E6]" /> : <Moon size={20} className="text-slate-750" />}
            </button>

            <Link href="/login" className="hidden rounded-full px-4 py-2 text-sm font-extrabold text-slate-650 dark:text-slate-400 transition-colors hover:text-[#41B6E6] sm:inline-flex">
              {t("entrar")}
            </Link>
            <Link href="/login" className="landing-blue-button inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm font-black text-white transition-transform hover:-translate-y-0.5">
              {t("acessar")}
              <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
            </Link>
          </div>
        </div>
      </nav>

      {/* ─── MAIN CONTENT ─── */}
      <main className="pt-[76px]">
        {/* Banner Hero */}
        <div className="relative border-b border-slate-100 dark:border-[#23262d] bg-slate-50 dark:bg-gradient-to-br dark:from-[#0c0c0e] dark:via-[#050608] dark:to-[#121318] px-5 py-[5.5rem] text-center md:px-8 transition-colors duration-300">
          <div className="mx-auto max-w-4xl">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-900/60 px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-slate-600 dark:text-slate-400">
              <span className="material-symbols-outlined text-sm">library_books</span>
              {t("badgeText")}
            </div>
            <h1 className="text-4xl font-black tracking-[-0.04em] text-slate-900 dark:text-white md:text-6xl font-headline">
              {t("refTitle")}
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-lg leading-8 text-slate-600 dark:text-zinc-400">
              {t("refSubtitle")}
            </p>
          </div>
        </div>

        <div className="mx-auto max-w-5xl px-5 py-[4.5rem] md:px-8">
          {/* Stack Tecnológico */}
          <section className="mb-[4.5rem]">
            <h2 className="mb-8 border-b border-slate-200 dark:border-zinc-800 pb-4 text-2xl font-black text-[#41B6E6] font-headline">
              {t("techTitle")}
            </h2>
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              <div className="rounded-[2.0rem] border border-slate-200 dark:border-[#23262d] bg-white dark:bg-[#0f1115] p-6 shadow-sm dark:shadow-none transition-all duration-300 hover:border-[#41B6E6]/40">
                <span className="material-symbols-outlined mb-3 text-3xl text-[#41B6E6]">developer_board</span>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">{t("techDesc1")}</h3>
                <p className="mt-2 text-sm leading-7 text-slate-600 dark:text-zinc-400">{t("techText1")}</p>
              </div>
              
              <div className="rounded-[2.0rem] border border-slate-200 dark:border-[#23262d] bg-white dark:bg-[#0f1115] p-6 shadow-sm dark:shadow-none transition-all duration-300 hover:border-[#41B6E6]/40">
                <span className="material-symbols-outlined mb-3 text-3xl text-[#41B6E6]">dns</span>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">{t("techDesc2")}</h3>
                <p className="mt-2 text-sm leading-7 text-slate-600 dark:text-zinc-400">{t("techText2")}</p>
              </div>
              
              <div className="rounded-[2.0rem] border border-slate-200 dark:border-[#23262d] bg-white dark:bg-[#0f1115] p-6 shadow-sm dark:shadow-none transition-all duration-300 hover:border-[#41B6E6]/40">
                <span className="material-symbols-outlined mb-3 text-3xl text-[#41B6E6]">robot_2</span>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">{t("techDesc3")}</h3>
                <p className="mt-2 text-sm leading-7 text-slate-600 dark:text-zinc-400">{t("techText3")}</p>
              </div>
              
              <div className="rounded-[2.0rem] border border-slate-200 dark:border-[#23262d] bg-white dark:bg-[#0f1115] p-6 shadow-sm dark:shadow-none transition-all duration-300 hover:border-[#41B6E6]/40">
                <span className="material-symbols-outlined mb-3 text-3xl text-[#41B6E6]">psychology</span>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">{t("techDesc4")}</h3>
                <p className="mt-2 text-sm leading-7 text-slate-600 dark:text-zinc-400">{t("techText4")}</p>
              </div>
            </div>
          </section>

          {/* Ferramentas e Arquiteturas */}
          <section className="mb-[4.5rem]">
            <h2 className="mb-8 border-b border-slate-200 dark:border-zinc-800 pb-4 text-2xl font-black text-[#41B6E6] font-headline">
              {t("openTitle")}
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {openSourceTools.map((item, idx) => (
                <div key={idx} className="rounded-[1.25rem] border border-slate-200 dark:border-[#23262d] bg-white dark:bg-[#0f1115] p-5 shadow-sm dark:shadow-none transition-colors hover:border-[#41B6E6]/40">
                  <h4 className="text-sm font-black text-slate-900 dark:text-white">{item.title}</h4>
                  <p className="mt-2 text-xs leading-relaxed text-slate-650 dark:text-zinc-400">{item.desc}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Bibliografia Científica */}
          <section>
            <h2 className="mb-8 border-b border-slate-200 dark:border-zinc-800 pb-4 text-2xl font-black text-[#41B6E6] font-headline">
              {t("bibTitle")}
            </h2>
            <div className="space-y-4">
              {references.map((ref) => (
                <div key={ref.id} className="group overflow-hidden rounded-[1.25rem] border border-slate-200 dark:border-[#23262d] bg-white dark:bg-[#0f1115] p-5 shadow-sm dark:shadow-none transition-colors hover:border-[#41B6E6]/40">
                  <p className="break-words text-justify text-sm leading-relaxed text-slate-650 dark:text-zinc-400">
                    {ref.text}
                  </p>
                  {ref.link && (
                    <a href={ref.link} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs font-bold text-[#41B6E6] hover:underline">
                      {t("docLink")} <span className="material-symbols-outlined text-[14px]">open_in_new</span>
                    </a>
                  )}
                </div>
              ))}
            </div>
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-100 dark:border-zinc-900 bg-slate-50 dark:bg-[#0c0c0e] py-8 text-center text-slate-500 dark:text-zinc-500 transition-colors duration-300">
        <p className="text-sm font-bold">{t("footerText").replace("{year}", new Date().getFullYear().toString())}</p>
      </footer>

      {/* Toast Notification */}
      <div 
        className={`fixed top-6 left-1/2 -translate-x-1/2 z-[9999] flex items-center gap-2.5 rounded-xl border border-[#41B6E6] bg-white dark:bg-[#111115] px-5 py-3.5 text-sm font-semibold text-slate-800 dark:text-white shadow-[0_12px_40px_rgba(65,182,230,0.18)] transition-transform duration-400 ease-[cubic-bezier(0.34,1.56,0.64,1)] ${
          showToast ? "translate-y-0 opacity-100" : "-translate-y-[200%] opacity-0"
        }`}
      >
        <svg className="w-5 h-5 text-[#41B6E6] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <circle cx="12" cy="12" r="10"/>
          <path d="M12 6v6l4 2"/>
        </svg>
        <span>{toastMsg}</span>
      </div>
    </div>
  );
}
