# Roadmap oficial da plataforma

Source of Truth da sequência estratégica de materialização do produto atualmente chamado Odisseus. O [Capability Map](docs/product/PLATFORM_CAPABILITY_MAP.md) mantém universo, estado factual, evidências, ownership e dependências das capacidades.

Revisão factual em 2026-10-23: baseline do lote offline do consumidor `dev`: `3fe0839dde5d4b0647992cda0e2fccaa412dfc8e`; evolução e limites descritos na [nota de desenvolvimento](docs/development/DEVELOPMENT_ENABLEMENT.md). Baseline institucional MOBS `009feb3558df7919070971656411f6c0a58cf8cf`. Identidade do source atual deve ser consultada no Git; identidade instalada, no manifesto do pacote, sem presumir equivalência. Datas identificam revisão, não compromisso de lançamento. A presença de código e testes isolados não certifica o E2E pelo Desktop.

## Direção e fronteiras

O objetivo é tornar a plataforma o ambiente principal de engenharia agêntica do fundador. Codex atual é baseline mínimo integral de capacidade de produto, não teto. A substituição cotidiana ocorre por fluxos reais concluídos; paridade integral inclui capacidades além de programação. Diferenciais próprios incluem governança MOBS, provenance e evolução verificável do próprio consumidor.

MOBS permanece autoridade institucional externa; o consumidor mantém runtime e produto. Roadmap não concede capabilities, altera OAP nem autoriza implementação. Cada ciclo exige mandato próprio. O AUTOMATION_ROADMAP do MOBS não é roadmap deste produto.

Self-Development é prioridade estratégica explícita: evoluir o próprio source em target separado. Self-Audit examina código e comportamento; Self-Update instala/ativa versões. Nenhum desses objetivos concede autoridade especial ao agente.

## Fases e critérios

Fases expressam dependências, não versões já entregues. Estado de ciclo pertence a este documento; estado de capacidade pertence ao Map. Preparação de trilhas pode ocorrer em paralelo quando suas garantias estiverem disponíveis.

| Fase | Objetivo e IDs do Map | Entrada | Saída verificável | Estado |
|---|---|---|---|---|
| F0 — Base operacional confiável | TEB física Windows, saúde, diagnóstico, segurança e UX de falhas (`execution`, `desktop`, `security`, `observability`) | Recursos, protocolo e isolamento suficientes; diagnóstico por evidência | Processo controlado inicia sob garantias exigidas; cancelamento/timeout cessam a unidade; efeitos são registrados; sem fallback inseguro | Parcial; testes isolados e correções presentes, Python pelo Desktop ainda não comprovado |
| F1 — Desenvolvimento cotidiano e Self-Development | Investigar, editar, testar/debug, reparar, revisar, promover e fechar Git (`repository`, `editing`, `validation`, `promotion`, `git-read`, `git-closure`, `review`, `self-development`) | F0 funcional, receitas/perfis e isolamento suficientes | Tarefas reais, inclusive no próprio source separado, concluídas com delta exato validado, provenance e fechamento Git autorizado | Próxima prioridade estratégica; base parcial existente |
| F2 — Continuidade e conhecimento | Durable execution, steering, Memory, Skills, Authority-Aware Context Engine, avaliação e Self-Audit (`continuity`, `memory`, `skills`, `context-intelligence`, `planning`, `evaluation`, `self-audit`) | Identidades e evidências reconstruíveis; fronteiras das fontes definidas | Retomada preserva mandato; contexto relevante, limitado e rastreável; falhas/achados avaliados sem autoampliar autorização | Planejada |
| F3 — Operação ampliada | Browser, Computer Use, automations, Specialists, Model Router, plugins/MCP e multi-agent (`browser`, `computer-use`, `automation`, `specialists`, `models`, `extensions`, `multi-agent`, `integrations`) | Execução confiável, política por ferramenta e provenance | Fluxos integrados observáveis, ações autorizadas, recuperação explícita e coordenação sem runtime paralelo | Planejada |
| F4 — Produção multimodal e games | Imagem/edição, referências, sprites/spritesheets, animação 2D/futura 3D, áudio, audiovisual, 3D, Visual Evaluation e games (`visual-input`, `images`, `sprites`, `animation`, `audio`, `video`, `three-d`, `visual-evaluation`, `games`, `artifacts`) | Perfis, ferramentas disponíveis, corpus curado quando necessário | Asset integrado e avaliado em contexto real, identidade/versão e sincronização; The Last Sentinel como campo de validação | Planejada |
| F5 — Acesso e evolução de instalações | Remote/mobile/voz, cloud/devboxes e Self-Update (`remote`, `voice`, `self-update`) | Segurança de acesso, continuidade e identidade de versão | Controle remoto preserva autorizações; atualização/ativação preserva dados e registra falha/recuperação | Planejada |

## Dependências e trilhas explícitas

- O bloqueio atual é a ausência de operação Python concluída pelo Desktop com cadeia de evidências. Há execução isolada anterior e correções de protocolo, contexto e toolchain; não atribuir toda falha à TEB ou à memória sem evento comprobatório. A integração de input do ambiente também permanece sem recuperação demonstrada. Preservar isolamento e fail-closed.
- A fatia local atual acrescenta exploração/busca por linha sobre leituras já carregadas, revisão conjunta de arquivos selados, catálogo observacional de receitas, custo de schemas por família e preparação de integridade de pacote. Isso não conclui F0/F1/F2, não implementa indexador do disco, reviewer independente ou promoção de N arquivos. Próximos experimentos e decisões estão na nota técnica de preparação, sem autoridade adicional.
- Self-Development em F1 mantém runtime ativo separado do target, vínculo confiável, artifact exato validado e promoção governada. A utilidade deve crescer para tarefas reais sem ampliar autoridade.
- Continuidade manual reúne referências e notas da conversa/workspace por cópia explícita. É preparação de trabalho, sem execução durável, retomada automática ou migração de autoridade; não satisfaz por si só a saída de F2.
- Git read precede closure. Branch/worktree, commit, push e PR exigem fatias e autorizações próprias; não decorrem deste planejamento.
- O roteamento mínimo por autoridade já existe. Authority-Aware Context Engine pertence a F2, antes da adoção de corpus em grande escala. Não exige criar novos corpus primeiro nem escolher banco vetorial neste ciclo.
- Model Router em F3 interage com Context Engine para modalidade, contexto, custo e capacidade; não decide autoridade.
- Browser/Computer Use usam observação, autorização, ação e verificação. Visual Evaluation pode começar nessa trilha e ser reutilizada em games e multimodalidade.
- Self-Audit em F2 produz achados e evidências, sem autoaprovar correções. Self-Update em F5 separa preparação, instalação e ativação; restart, migração e recuperação exigem decisão específica.
- Corpus especializados serão curados por necessidade. Skills aplicam workflows; Specialists assumem papéis; modelos inferem; Project Profiles fornecem defaults; ferramentas executam; Evaluators confrontam evidências.
- Capability Harvest é contínuo (`capability-harvest`): descoberta factual → Map → priorização → mandato de implementação. Novas capacidades ainda desconhecidas recebem posição após evidência, sem implementação implícita.

## Itens herdados preservados ou reclassificados

O conteúdo anterior deste path permanece recuperável pelo Git. Não há LEGACY_ROADMAP nem backlog legado paralelo.

| Itens herdados | Destino |
|---|---|
| Bugs, fresh-install smoke, onboarding, empty states e erros claros | F0: confiabilidade; plataformas adicionais somente com garantias verificadas |
| Prompt/context bloat, seleção de tools e carga de Skills | F2: Context Intelligence, budgeting e carga progressiva |
| Prompt injection e ferramentas administrativas | Segurança transversal F0–F3; conteúdo recuperado não concede autoridade |
| Provider probing e degraded states de ChromaDB/SearXNG/email/ntfy | F0: diagnóstico; F3: providers/extensões |
| Backup/restore de data | F0 e requisito de Self-Update em F5 |
| Scheduler, Notes/Todos e tarefas por agente | F2–F3: continuidade e automations; reutilizar backend útil |
| Acessibilidade, foco, teclado, modal/layout, mobile | F0 no fluxo principal; F5 para acesso mobile |
| Editor, arquivos, export e previews | F1: engenharia; F4: artefatos |
| Research por hardware, Cookbook/serving/SGLang e model ranking | F3: modelos/extensões; F5: ambientes remotos, por demanda |
| Speculative decoding | Condicional em F3 após medir qualidade, tempo de conclusão e compatibilidade |
| Integrações e performance de Email | F3: admissão por caso de uso; otimização condicionada à demanda |
| Gallery/editor, inpaint e mobile | F4: produção visual; F5: acesso mobile |
| Assets CDN/offline | F0/F5 quando exigido pela instalação suportada |
| CSS, tours, dead code e refactors genéricos | Retirados como objetivos autônomos; manutenção por defeito demonstrado |
| Humor, preferência sobre temas e exemplos históricos de modelos | Descartados da direção vigente; recuperáveis pelo Git |

## Manutenção e autorização

Fundador decide direção estratégica; maintainers delegados mantêm ciclos de seu escopo. Critérios de saída exigem resultados e evidências, não apenas código presente. O benchmark deve ser revisto com fonte/data e disponibilidade por ambiente. Paridade de responsabilidade não exige copiar arquitetura interna ou interface. Segurança, provenance, UX e independência de modelo atravessam todas as fases.
