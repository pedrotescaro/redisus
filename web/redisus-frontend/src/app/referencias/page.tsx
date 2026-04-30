import Link from "next/link";
import Image from "next/image";
import { ThemeToggle } from "@/components/theme-toggle";

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
  }
];

export default function ReferenciasPage() {
  return (
    <div className="min-h-screen bg-surface text-on-surface">
      <nav className="fixed top-0 z-50 w-full bg-surface/80 backdrop-blur-xl shadow-ambient border-b border-outline-variant/10">
        <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between px-6">
          <Link href="/" className="group flex items-center gap-2">
            <Image
              src="/images/logo.png"
              alt="Heal+ Logo"
              width={56}
              height={56}
              className="transition-transform group-hover:scale-105"
            />
            <div className="-ml-1">
              <h1 className="text-2xl font-extrabold leading-none tracking-tight text-primary font-headline">
                Heal+
              </h1>
              <p className="mt-0.5 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant opacity-70">Plataforma Clínica</p>
            </div>
          </Link>
          <div className="flex items-center gap-4">
            <ThemeToggle />
            <Link href="/" className="inline-flex items-center gap-2 pl-4 border-l border-outline-variant/20 text-sm font-semibold hover:text-primary transition-colors">
              <span className="material-symbols-outlined text-[18px]">arrow_back</span>
              Voltar
            </Link>
          </div>
        </div>
      </nav>

      <main className="mx-auto max-w-4xl px-6 pt-36 pb-24">
        <div className="mb-14 text-center">
          <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-1.5 text-xs font-bold uppercase tracking-widest text-primary mb-6">
            <span className="material-symbols-outlined text-sm">library_books</span>
            Fundamentação e Tecnologia
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight font-headline md:text-5xl text-on-surface">
            Referências do Trabalho
          </h1>
          <p className="mt-4 text-lg text-on-surface-variant max-w-2xl mx-auto">
            Base teórica, protocolos clínicos e arquitetura tecnológica completa que estruturam a plataforma HEAL+.
          </p>
        </div>

        <section className="mb-16">
          <h2 className="text-2xl font-bold font-headline mb-8 border-b border-outline-variant/20 pb-4 text-primary">Stack Tecnológico e IA</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="rounded-2xl border border-outline-variant/20 bg-surface-container p-6">
              <span className="material-symbols-outlined text-tertiary text-3xl mb-3">developer_board</span>
              <h3 className="text-lg font-bold">Frontend (Web Portal)</h3>
              <p className="mt-2 text-sm text-on-surface-variant">Desenvolvido em Next.js 14, React 18 e Tailwind CSS, oferecendo uma experiência moderna com App Router e design adaptativo (Light/Dark mode).</p>
            </div>
            
            <div className="rounded-2xl border border-outline-variant/20 bg-surface-container p-6">
              <span className="material-symbols-outlined text-secondary text-3xl mb-3">dns</span>
              <h3 className="text-lg font-bold">Backend & Infraestrutura</h3>
              <p className="mt-2 text-sm text-on-surface-variant">Arquitetura sustentada por Python (Flask API), banco de dados em tempo real NoSQL (Firebase Firestore) e Storage na nuvem do Google Cloud.</p>
            </div>
            
            <div className="rounded-2xl border border-outline-variant/20 bg-surface-container p-6">
              <span className="material-symbols-outlined text-primary text-3xl mb-3">robot_2</span>
              <h3 className="text-lg font-bold">Modelos de Visão Computacional</h3>
              <p className="mt-2 text-sm text-on-surface-variant">Implementação de algoritmos de Deep Learning e Visão Computacional (OpenCV, YOLOv8 e ResNet50) para avaliação tecidual clínica.</p>
            </div>
            
            <div className="rounded-2xl border border-outline-variant/20 bg-surface-container p-6">
              <span className="material-symbols-outlined text-primary text-3xl mb-3">psychology</span>
              <h3 className="text-lg font-bold">Inteligência Artificial (LLM)</h3>
              <p className="mt-2 text-sm text-on-surface-variant">Uso avançado de IA Generativa (Google Gemini 2.0 Flash) processando análise multimodal (dados e texto) integrado como agente de apoio à decisão.</p>
            </div>
          </div>
        </section>

        <section className="mb-16">
          <h2 className="text-2xl font-bold font-headline mb-8 border-b border-outline-variant/20 pb-4 text-primary">Ferramentas e Arquiteturas Open-Source</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="rounded-xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-ambient hover:border-primary/30 transition-colors">
               <h4 className="font-bold text-on-surface text-sm">YOLOv8 & Ultralytics</h4>
               <p className="mt-1 text-xs text-on-surface-variant leading-relaxed">Detecção de objetos em tempo real em duas vias para identificação estrutural e localização primária da lesão no quadro.</p>
            </div>
            <div className="rounded-xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-ambient hover:border-primary/30 transition-colors">
               <h4 className="font-bold text-on-surface text-sm">BiomedCLIP (Microsoft)</h4>
               <p className="mt-1 text-xs text-on-surface-variant leading-relaxed">Análise zero-shot multimodal construída com base em linguagem de visão unificada adaptada exclusivamente para o domínio biomédico.</p>
            </div>
            <div className="rounded-xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-ambient hover:border-primary/30 transition-colors">
               <h4 className="font-bold text-on-surface text-sm">MedSAM</h4>
               <p className="mt-1 text-xs text-on-surface-variant leading-relaxed">Modelo base de IA adaptado da arquitetura genérica SAM (Segment Anything) voltado à segmentação granular de bordas em imagens médicas.</p>
            </div>
            <div className="rounded-xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-ambient hover:border-primary/30 transition-colors">
               <h4 className="font-bold text-on-surface text-sm">DermaIntel ViT</h4>
               <p className="mt-1 text-xs text-on-surface-variant leading-relaxed">Classificador de ferimentos cutâneos baseado em arquitetura moderna de Transformadores Visuais (Vision Transformers - Hugging Face).</p>
            </div>
            <div className="rounded-xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-ambient hover:border-primary/30 transition-colors">
               <h4 className="font-bold text-on-surface text-sm">MediaPipe</h4>
               <p className="mt-1 text-xs text-on-surface-variant leading-relaxed">Framework rápido para rastreamento holístico e detecção de pontos articulares para enquadramento do paciente acamado.</p>
            </div>
            <div className="rounded-xl border border-outline-variant/10 bg-surface-container-low p-5 shadow-ambient hover:border-primary/30 transition-colors">
               <h4 className="font-bold text-on-surface text-sm">HL7 FHIR R4</h4>
               <p className="mt-1 text-xs text-on-surface-variant leading-relaxed">Conjunto de padrões internacionais de interoperabilidade semântica (em estruturação) para troca de dados de prontuário com o DATASUS.</p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-bold font-headline mb-8 border-b border-outline-variant/20 pb-4 text-primary">Bibliografia Científica</h2>
          <div className="space-y-4">
            {references.map((ref) => (
              <div key={ref.id} className="group rounded-xl border border-outline-variant/10 bg-surface-container-lowest p-6 hover:border-primary/30 transition-colors">
                <p className="text-sm leading-relaxed text-on-surface-variant text-justify">
                  {ref.text}
                </p>
                {ref.link && (
                  <a href={ref.link} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline">
                    Ver documento <span className="material-symbols-outlined text-[14px]">open_in_new</span>
                  </a>
                )}
              </div>
            ))}
          </div>
        </section>

      </main>
      
      <footer className="border-t border-outline-variant/10 bg-surface-container-lowest py-8 text-center">
        <p className="text-sm text-on-surface-variant">© {new Date().getFullYear()} HEAL+ REDISUS.</p>
      </footer>
    </div>
  );
}
