# Correções de Interface - Relatório de Erros de Design (Reports Form)

## Status Geral
✅ **Plano aprovado e em execução**

## Passos do Plano (Breakdown)

### 1. Editar globals.css (Prioridade Alta) ✅
- [x] Aplicar bordas sutis dark mode (#444/20%)
- [x] Classe `.outline-export` para botão DOCX
- [x] Estilos hover globais para inputs/cards/buttons

### 2. Editar reports/page.tsx (Prioridade Alta) ✅
- [x] Ajustar classes botão Exportar DOCX (text-[#999])
- [x] Garantir hover em cards/elements (card-hover class)

### 3. Editar UI Components (Opcional se globals cobrir) ✅
- [x] globals.css expandido: .dark .border*, .bg-white, table tr, legacy slate/brand → #444/20-30%
- [x] Dashboard cards: ghost-border + card-hover adicionados

### 4. Testes & Validação
- [ ] `cd web/redisus-frontend && npm run dev`
- [ ] Testar dark mode: bordas sutis, DOCX discreto (cinza), PDF azul primário
- [ ] Hover: mudança bg clara + borda azul em inputs/select/cards/buttons
- [ ] Contrastes: mínimo, definição sem gritar
- [ ] Responsivo/light mode intacto

### 5. Finalização
- [ ] Atualizar TODO.md ✅
- [ ] attempt_completion com demo cmd

**Responsável**: BLACKBOXAI  
**Data**: Em andamento
