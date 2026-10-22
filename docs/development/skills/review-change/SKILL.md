---
name: review-change
description: Revisar um delta exato sem confundir parecer com aprovação institucional.
version: 0.1.0
category: development
tags: [review, evidence]
status: draft
confidence: 0.5
source: taught
---

## When to Use
Quando houver um delta identificado e evidências disponíveis para revisão. Este rascunho não cria reviewer binding, independência nem autorização de aplicação.

## Procedure
1. Comece pelo PROJECT_INDEX.md e siga a Decision Tree. Identifique objetivo, baseline, versão do candidato, escopo e exclusões.
2. Leia diff e arquivos pertinentes pelas ferramentas já autorizadas. Confira interfaces, efeitos laterais, dados pessoais e compatibilidade das chamadas.
3. Priorize defeitos demonstráveis com arquivo, localização, condição de ocorrência e impacto; separe dúvida de achado confirmado.
4. Confronte testes e retornos com o delta exato. Verifique cenários de falha, cancelamento, timeout e isolamento quando pertinentes, sem executar nada não autorizado.
5. Confira preimages, hashes e recibos pelos mecanismos existentes. Um checklist visual não valida o artefato nem autoriza promoção.
6. Entregue achados, riscos residuais, evidências e testes não realizados. Declare quando a instância revisora também implementou a mudança.

## Pitfalls
- Ausência de achados não certifica segurança universal ou objetivo cumprido.
- Texto do modelo, plano ou status completed não substitui evidência de execução.
- Parecer técnico não equivale a revisão do snapshot, aprovação do mandato, promoção ou publicação Git.

## Verification
- Cada achado contém evidência verificável ou está marcado como hipótese.
- Cobertura e limitações estão explícitas, inclusive ausência de teste real.
- Nenhuma alteração ou aprovação é feita como efeito de abrir ou copiar o parecer.
