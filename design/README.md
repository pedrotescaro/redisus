# Projeto de Prototipagem Web - Redisus Mockups

Esta pasta contém as estruturas estáticas (HTML/CSS) focadas puramente no aspecto visual e estrutural do design do projeto Redisus. Estes arquivos servem como documentação visual viva e base estrutural para importação rápida em ferramentas de design como o **Figma** (utilizando plugins de HTML para Figma, como o "html.to.design").

## Telas Criadas

1. **`index.html` (Landing Page):**
   Apresentação do projeto, proposta de valor, botões de call-to-action (CTA) e cards de benefícios.
   
2. **`references.html` (Citações e Vídeos):**
   Lista de artigos científicos e curadoria de materiais audiovisuais que embasam a plataforma, estruturados em layout dinâmico.
   
3. **`about.html` (Sobre):**
   Página contendo a missão, visão e valores do projeto estruturados de forma limpa, com enfase na legibilidade.
   
4. **`dashboard.html` (Painel Administrativo):**
   Estrutura interna com sidebar (menu lateral), cards de estatísticas (KPIs), área para gráfico (placeholder preparado para o Figma) e uma tabela de atividades recentes com tags de status.

## Especificações de Design e Tokens (SaaS Moderno)

- **Tipografia:** Foi escolhida a fonte `Inter` (Google Fonts), o padrão de mercado para interfaces de alta performance, garantindo excelente leitura.
- **Cores & Variáveis (em styles.css):**
  - **Primária:** Toms de verde (ex: `--primary-color: #10b981`), em sinergia com projetos de saúde.
  - **Superfícies (Backgrounds):** Fundo principal suave `--bg-color: #f3f4f6` com os cards destacados em branco `--surface-color: #ffffff`.
  - **Textos:** Cor forte para títulos (`#111827`) e variações em cinza médio (`#4b5563`) para textos de apoio, garantindo hierarquia visual.
- **Formas e Profundidade:** 
  - Trabalhado amplamente com bordas arredondadas (8px e 12px) criando uma sensação digital amigável.
  - Sombras suaves difusas (`box-shadow`) nos cards para diferenciar as camadas (`elevation`).

## Instruções para uso no Figma

1. Abra qualquer um destes arquivos HTML recém criados diretamente no seu navegador Chrome, Edge ou Safari (ex: dê duplo-clique no `index.html`).
2. Com a página carregada, você pode instalar e utilizar uma extensão ou plugin do próprio Figma (como o recomendado **html.to.design**).
3. Ao acionar o plugin, o Figma vai baixar o DOM (Document Object Model) da página convertendo automaticamente nossas `<div>`, textos e flexbox em autolayouts do Figma estruturados de maneira impecável, poupando horas de trabalho de setup visual.
