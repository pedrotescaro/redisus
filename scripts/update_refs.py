import re

# The user's original 12 references
user_refs = [
    { "id": 1, "text": "ARAÚJO, T. M. et al. Realidade virtual no alívio da dor durante a troca de curativos de feridas crônicas. Revista da Escola de Enfermagem da USP, São Paulo, v. 55, e20200513, 2021. DOI: https://doi.org/10.1590/1980-220X-REEUSP-2020-0513. Disponível em: https://www.scielo.br/j/reeusp/a/xLqsRvkycBVLt3DD7BsM4tP/?lang=pt&format=pdf. Acesso em: 30 maio 2025.", "link": "https://www.scielo.br/j/reeusp/a/xLqsRvkycBVLt3DD7BsM4tP/?lang=pt&format=pdf" },
    { "id": 2, "text": "BORGES, Eline Lima; SOUZA, Perla Oliveira Soares de. Feridas: como tratar. 3. ed. Rio de Janeiro: Rubio, 2024. p. 61-88." },
    { "id": 3, "text": "FLORIANÓPOLIS. Prefeitura Municipal. Secretaria Municipal de Saúde. Protocolo de cuidados de feridas. Florianópolis, SC: SMS, 2008." },
    { "id": 4, "text": "GERMANO, Renan Soares; ELISEO, Maria Amelia; SILVEIRA, Ismar Frango. Introdução à acessibilidade na Web: do conceito à prática. In: JORNADAS IBERO-AMERICANAS DE INTERAÇÃO HUMANO-COMPUTADOR, 7., 2021, São Paulo. Anais [...]. São Paulo: Sociedade Brasileira de Computação, 2021." },
    { "id": 5, "text": "LIMA, E. V. M. et al. Construction of a mobile application for wound assessment for nursing students and professionals. Estima – Brazilian Journal of Enterostomal Therapy, [S. l.], v. 22, art. 1515, 2024. Disponível em: https://www.revistaestima.com.br/estima/article/view/1515. Acesso em: 1 nov. 2024.", "link": "https://www.revistaestima.com.br/estima/article/view/1515" },
    { "id": 6, "text": "MADRIL MEDEIROS, R. M. et al. Contribuição de um software para o registro, monitoramento e avaliação de feridas. Global Academic Nursing Journal, [S. l.], v. 2, n. 3, p. e146, 2021. DOI: 10.5935/2675-5602.20200146. Disponível em: https://www.globalacademicnursing.com/index.php/globacadnurs/article/view/123. Acesso em: 7 mar. 2025.", "link": "https://www.globalacademicnursing.com/index.php/globacadnurs/article/view/123" },
    { "id": 7, "text": "MEDETEC. Medetec Image Databases. A collection of wound images for research and education. Disponível em: https://www.medetec.co.uk/files/medetec-image-databases.html.", "link": "https://www.medetec.co.uk/files/medetec-image-databases.html" },
    { "id": 8, "text": "MENOITA, E.; SEARA, A.; SANTOS, V. Plano de Tratamento dirigido aos Sinais Clínicos da Infecção da Ferida. Journal of Aging & Inovation, v. 3, n. 2, p. 62-73, 2014." },
    { "id": 9, "text": "PAULA, M. A. B.; SANTOS, V. L. C. G. O significado de ser especialista para o enfermeiro estomaterapeuta. Revista Latino-Americana de Enfermagem, Ribeirão Preto, v. 11, n. 4, p. 474–482, jul. 2003. Disponível em: https://www.scielo.br/j/rlae/a/mvBJQ3wFgTGjT6hJ4NNDVxS/. Acesso em: 13 nov. 2024.", "link": "https://www.scielo.br/j/rlae/a/mvBJQ3wFgTGjT6hJ4NNDVxS/" },
    { "id": 10, "text": "ROCHA, Adiel Andrade. Feridômetro: aplicativo de auxílio à aprendizagem do acrônimo TIMERS. 2021. Trabalho de Conclusão de Curso (Graduação em Ciência da Computação) – Universidade Federal de Campina Grande, Campina Grande, 2021. Disponível em: https://dspace.sti.ufcg.edu.br/bitstream/riufcg/19691/1/ADIEL%20ANDRADE%20ROCHA%20-%20TCC%20CI%C3%8ANCIA%20DA%20COMPUTA%C3%87%C3%83O%202021.pdf. Acesso em: 2 set. 2025.", "link": "https://dspace.sti.ufcg.edu.br/bitstream/riufcg/19691/1/ADIEL%20ANDRADE%20ROCHA%20-%20TCC%20CI%C3%8ANCIA%20DA%20COMPUTA%C3%87%C3%83O%202021.pdf" },
    { "id": 11, "text": "SILVA, Cláudio Xavier da. Sis-MF - Aplicativo para monitoramento da cicatrização de feridas. 2018. Dissertação (Mestrado Profissional em Ciências) – Universidade Federal de São Paulo, São Paulo, 2018." },
    { "id": 12, "text": "SOARES PACZEK, R. et al. A ESTOMATERAPIA COMO CAMPO DE ESTÁGIO. In: CONGRESSO BRASILEIRO DE ESTOMATERAPIA, [S. l.], 2024. Anais [...]. [S. l.]: SOBEST, 2024. Disponível em: https://anais.sobest.com.br/cbe/article/view/447. Acesso em: 20 out. 2024.", "link": "https://anais.sobest.com.br/cbe/article/view/447" }
]

readme_path = r"c:\Users\PEDRO\Documents\redisus\README.md"
page_path = r"c:\Users\PEDRO\Documents\redisus\web\redisus-frontend\src\app\referencias\page.tsx"

with open(readme_path, "r", encoding="utf-8") as f:
    readme_content = f.read()

# Extract from README
ref_section_idx = readme_content.find("## 20. Referências Bibliográficas")
refs_text = readme_content[ref_section_idx:]

extracted_refs = []
lines = refs_text.split('\n')
for line in lines:
    line = line.strip()
    match = re.match(r'^(\d+)\.\s+\*\*(.*?)\*\*\s+(.*)$', line)
    if match:
        author = match.group(2)
        desc = match.group(3)
        text = f"{author} {desc}"
        # Extract link if any (like https:// or doi:)
        link = None
        link_match = re.search(r'(https?://[^\s]+)', text)
        if link_match:
            link = link_match.group(1).rstrip('.')
        
        extracted_refs.append({"text": text, "link": link})

all_refs = user_refs[:]
idx = 13
for r in extracted_refs:
    # Add to list
    nr = {"id": idx, "text": r["text"]}
    if r["link"]:
        nr["link"] = r["link"]
    all_refs.append(nr)
    idx += 1

# Generate the TSX array string
tsx_array = "const references = [\n"
for i, r in enumerate(all_refs):
    tsx_array += "  {\n"
    tsx_array += f'    id: {r["id"]},\n'
    tsx_array += f'    text: "{r["text"].replace('"', '\\"')}"'
    if "link" in r:
        tsx_array += f',\n    link: "{r["link"]}"\n'
    else:
        tsx_array += "\n"
    tsx_array += "  }"
    if i < len(all_refs) - 1:
        tsx_array += ","
    tsx_array += "\n"
tsx_array += "];"

# Update page.tsx
with open(page_path, "r", encoding="utf-8") as f:
    page_content = f.read()

page_content = re.sub(r'const references = \[.*?\];', tsx_array, page_content, flags=re.DOTALL)

with open(page_path, "w", encoding="utf-8") as f:
    f.write(page_content)


# Generate the new Markdown for README
md_refs = "## 20. Referências Bibliográficas\n\n"
for r in all_refs:
    # formatting for readme
    md_refs += f"{r['id']}. {r['text']}\n"
    
new_readme_content = readme_content[:ref_section_idx] + md_refs + "\n---\n\n<p align=\"center\">\n  <strong>HEAL+ / REDISUS</strong> — Cluster 7 REDI-SUS — RNP/RUTE<br>\n  Rede de Pesquisa em Saúde Digital Inteligente<br>\n  Diagnóstico, Planos de Cuidado e Acompanhamento Remoto<br>\n  <em>Fatec Ferraz de Vasconcelos — Módulo HEAL+ (PT2 + PT7)</em>\n</p>\n"

with open(readme_path, "w", encoding="utf-8") as f:
    f.write(new_readme_content)

print(f"Success! Integrated {len(all_refs)} references into both page.tsx and README.md.")
