---
name: implement-change
description: Preparar mudança pequena e coesa com revisão e validação rastreáveis.
version: 0.1.0
category: development
tags: [implementation, review]
status: draft
confidence: 0.5
source: taught
---

## When to Use
Quando existir solicitação autorizada de alteração no projeto selecionado. Este rascunho não substitui autoridades, receitas nem autorização de execução ou promoção.

## Procedure
1. Comece pelo PROJECT_INDEX.md e siga a Decision Tree. Registre resultado esperado, exclusões, baseline e arquivos afetados antes de editar.
2. Inspecione interfaces e convenções pertinentes dentro do escopo permitido. Prefira mecanismos existentes; não crie runtime, serviço ou protocolo alternativo por conveniência.
3. Planeje uma mudança coesa; exponha dependências entre arquivos. Limite a promoção às capacidades existentes, sem dividir uma mudança atômica para contornar limites.
4. Faça alterações somente no target privado admitido pela TEB. Preserve preimages e não modifique o executor ativo ou dados pessoais.
5. Defina testes conforme TEST_EXECUTION_MODEL.md antes de executar. Use somente receitas admitidas, recursos suficientes e autorizações válidas.
6. Revise o delta exato, resultados e limitações. Relacione arquivos e operações por evidências, sem marcar o plano como prova automática.
7. Prepare o artefato selado e seus recibos pelo fluxo existente. Promoção, fechamento Git e ativação são decisões separadas; não os infira deste workflow.

## Pitfalls
- O mecanismo atual de promoção aceita um arquivo ou exatamente dois; uma alteração que exija mais arquivos precisa de decisão própria.
- Testes locais do assistente não comprovam o E2E do Desktop nem constituem recibo institucional do artefato.
- Proposta, versão, snapshot, revisão e autorização não são intercambiáveis.

## Verification
- Delta corresponde ao objetivo e respeita baseline, paths e exclusões.
- Resultados identificam comandos realmente executados, retorno, versão e regressões pertinentes.
- Relatório distingue preparado, validado, promovido e instalado; não declara etapas ausentes.
