# Platform Capability Map

Source of Truth do universo de capacidades da plataforma atualmente chamada Odisseus: estado factual, evidência, natureza arquitetural, dependências, risco, ownership e cobertura. A ordem de materialização pertence exclusivamente ao [ROADMAP.md](../../ROADMAP.md).

Revisão factual em 2026-10-22: consumidor `dev` em `5bb4f80e3ba782c4f1be07db946eb986f1341e85`, mais o delta local descrito na [preparação do desenvolvimento](../development/DEVELOPMENT_ENABLEMENT.md); MOBS `main` em `009feb3558df7919070971656411f6c0a58cf8cf`. Estado descreve inspeção do código e evidências delimitadas; não certifica cada fluxo operacional nem acompanha novos commits automaticamente. O benchmark externo ao final continua datado de 2026-10-11.

## Baseline e responsabilidades

Codex atual é baseline mínimo integral de capacidade de produto, não teto. Toda classe relevante descoberta entra no Map, mesmo sem implementação imediata. Diferenciais próprios e novas modalidades recebem o mesmo tratamento. Cobertura estratégica não equivale a capability profile, permissão, ferramenta disponível ou execução garantida.

Fundador responde pela direção do produto; maintainer do consumidor mantém estado/evidências. Owner técnico abaixo é responsabilidade de manutenção, não delegação institucional; pessoas são atribuídas por mandato. MOBS conserva autoridade institucional, consumidor materializa runtime/produto.

Estados: **existente** = mecanismo implementado; **parcial** = responsabilidade incompleta; **herdado** = superfície presente sem integração governada demonstrada; **ausente** = implementação não identificada no escopo auditado. Nenhum estado isolado significa teste operacional aprovado. Cobertura **mapeada** registra responsabilidade; detalhes/evidências ainda insuficientes ficam explícitos.

## Capability Parity Matrix

Benchmark: **D** = documentado nas fontes oficiais; **O** = observado nas ferramentas/Skills deste ambiente Codex, sujeito à configuração; **E** = expansão própria, sem alegar capacidade nativa equivalente. O Roadmap referencia os IDs; prioridades de implementação não pertencem a esta matriz.

| ID / capacidade | Benchmark | Estado e evidência consumidora | Natureza / owner técnico | Dependências; risco | Cobertura |
|---|---|---|---|---|---|
| `conversation` — Chat, sessões e anexos | D/O | Existente; chat/session routes e UI | Produto/runtime; UI/chat | Auth, modelo e persistência; perda de estado | Mapeada |
| `desktop` — Desktop, instalação e UX | D | Existente; `src/desktop_host.py`, `desktop/`, Product Shell e temas | Produto/deployment; Desktop | Backend/WebView2/data; boot ou compatibilidade | Mapeada |
| `repository` — Workspace, arquivos, busca e compreensão | D/O | Parcial; filesystem tools, workspace boot e visão do escopo da proposta em `studioEngineering.js`; sem novo indexador ou leitura automática | Runtime/tools; engenharia | Paths, contexto e baseline; leitura indevida | Mapeada |
| `editing` — Patching e edição coesa | D/O | Parcial; Agent Loop/dispatcher e edição privada | Tools/runtime; engenharia | TEB/Promotion; bypass ou delta incompleto | Mapeada |
| `execution` — Terminal/processos, ambiente e efeitos | D/O | Parcial; Windows Native e toolchain corrigida; execução isolada não comprova Python pelo Desktop, ainda pendente | Runtime/TEB; fronteira | Isolamento, árvore, rede, paths; escape/efeitos incertos | Mapeada; E2E requer validação |
| `validation` — Testes, lint, compile, build e debug | D/O | Parcial; pytest, py_compile, Ruff; profile v6 | Receitas/perfis; comandos | Tool disponível e TEB; execução indireta | Mapeada |
| `promotion` — Delta selado e aplicação | E | Parcial; single-file e exatamente dois create/write | Runtime; Promotion | Mandato/OAP/hashes/preimage/drift; aplicação parcial | Mapeada |
| `git-read` — Identidade/status/diff/log/show | D/O | Parcial; branch/HEAD/status tipados; demais ausentes | Tools/perfis; Git | Metadata/baseline/read paths; helpers e vazamento | Mapeada |
| `git-closure` — Worktrees, branches, commit/push/PR/CI | D/O | Ausente como fluxo governado | Runtime/integração; engenharia | Git read, isolamento e autorização; publicação/perda | Mapeada |
| `review` — Code review e segurança | D/O | Checklist consultivo e artefatos inspecionáveis parciais; reviewer especializado governado ausente | Specialist/tools; review | Delta/contexto/evidência; achados omitidos ou inventados | Mapeada |
| `planning` — Plano multi-step e replanejamento | D/O | Parcial; Agent Loop/instruções e planos junto a registros de ferramentas em `studioActivity.js`; sem vínculo por etapa nem planner confiável dedicado | Runtime; Agent Loop | Mandato/avaliação; plano ampliar escopo | Mapeada |
| `evaluation` — Resultado, debugging e reparo iterativo | D/O | Parcial; validações específicas, ciclo geral incompleto | Runtime/evaluator; avaliação | Critérios/evidências; falso sucesso | Mapeada |
| `continuity` — Durable runs, steering, fila e retomada | D/O | Parcial; sessões/agent_runs não provam durable execution MOBS completo | Runtime/persistência; runs | Contexto/ledger/cancelamento; ação repetida ou obsoleta | Mapeada |
| `automation` — Agendamento/background/monitoramento | D/O | Herdado/parcial; task_scheduler/bg_jobs | Runtime/produto; tarefas | Durable runs/policy; efeitos sem aprovação | Mapeada |
| `memory` — Memória operacional e de projeto | D | Parcial; memory/provider/vector | Memory/runtime; conhecimento | Origem/escopo/contexto; memória virar autoridade | Mapeada |
| `skills` — Workflows e recursos | D/O | Parcial; skills routes e integrações; três templates de desenvolvimento em docs, não instalados nem publicados | Skills; extensões | Tools/corpus/trust; prompt injection | Mapeada |
| `context-intelligence` — Authority-Aware Context Engine | E; contexto/memória D | Parcial: boot authority-first e diagnóstico de peso/duplicatas literais existem; engine completo ausente | Runtime; contexto | Fontes/identidades/permissões; omissão, custo e vazamento | Mapeada; implementação aberta |
| `models` — Providers, discovery, escolha/fallback/routing | D | Parcial; endpoints/discovery/MOBS Auto; Auto seleciona o mesmo Qwen coder, não compara custo/complexidade entre modelos | Router/modelos; providers | Contexto/modalidade/qualidade/custo; escolha inadequada | Mapeada |
| `extensions` — Plugins/MCP/hooks/conectores | D/O | Parcial; MCP routes/servers e integrações | MCP/plugins/tools; extensões | Auth/admissão/policy; expansão de efeitos | Mapeada |
| `browser` — Pesquisa, navegação e debugging web | D/O | Parcial; search/Deep Research; browser governado ausente | Tools/runtime; web | Rede/DOM/auth/evidências; conteúdo não confiável | Mapeada |
| `computer-use` — Screenshot/UIA/mouse/teclado | D/O | Ausente como capacidade própria governada | Runtime/adapters/tools; Computer Use | Observação/policy/verificação; alvo errado | Mapeada |
| `visual-input` — Fotos/imagens/referências | D/O | Parcial; uploads/imagens | Produto/modelos; multimodal | Leitura/identidade; exposição/interpretação | Mapeada |
| `remote` — Remote/mobile/cloud/devboxes | D | Ausente como control plane governado; SSH/Cookbook herdados | Produto/infra; deployment | Auth/durable runs/ambiente; serviços e credenciais | Mapeada |
| `voice` — Interação por voz | D | Parcial; STT/TTS routes | Produto/serviços; multimodal | Sessões/consentimento; comando mal transcrito | Mapeada |
| `multi-agent` — Delegação/paralelismo/handoff | D/O | Herdado/parcial; Group Chat não prova coordenação MOBS | Runtime; coordenação | Ownership/runs/contexto; conflito/duplicação | Mapeada |
| `specialists` — Papéis por disciplina | E | Parcial; personas não demonstram especialistas operacionais | Specialist/workflows; disciplina | Skills/corpus/tools/modelos; identidade virar autoridade | Mapeada |
| `images` — Geração/edição de imagens | D: geração/edição com referências e Skill imagegen; disponibilidade por superfície | Herdado/parcial; Gallery/editor e image models | Tools/serviços/modelos; multimodal | Referência/provedor/provenance; qualidade/identidade | Mapeada |
| `sprites` — Sprites/spritesheets/assets 2D | E | Pipeline governado ausente; The Last Sentinel demonstra demanda | Specialist/tools; assets | Perfil/import/avaliação; inconsistência/desalinhamento | Mapeada |
| `animation` — Animação 2D/futura 3D | E | Pipeline ausente; Animation System é referência candidata | Corpus/Skills/Specialist/tools; animação | Poses/timing/engine; frames substituir qualidade | Mapeada |
| `audio` — SFX/música/edição | E; voz D | Produção ausente, STT/TTS parcial | Serviços/modelos/tools; áudio | Provenance/integração; autoria/sincronização | Mapeada |
| `video` — Vídeo/audiovisual | E | Ausente | Serviços/modelos/tools; audiovisual | Assets/áudio/timeline/avaliação; custo/consistência | Mapeada |
| `three-d` — Modelagem/materiais/texturas/rigging/render | E | Ausente | Specialist/tools/modelos; 3D | Toolchain/perfil/avaliação; rig/geometria incompatíveis | Mapeada |
| `visual-evaluation` — Avaliação visual/gameplay | E; inspeção visual O | Ciclo próprio governado ausente | Evaluator/tools; avaliação visual | Observação/referência/critérios; julgar sheet sem gameplay | Mapeada |
| `games` — Engines/Godot/testes/assets | D: workflow de browser games via Skills de design, implementação, assets e playtest; E: pipeline governado próprio, incluindo Godot | Profile Godot conservador sem receita engine admitida; requisitos comuns e estudos Unity/Unreal na nota de preparação; Godot local 4.7.2 identificado, sem execução do projeto | Perfis/tools/Skills; engenharia/disciplinas | TEB/comandos/assets/gameplay; hardcodes por jogo | Mapeada; suporte operacional não comprovado |
| `artifacts` — Docs/PDF/planilhas/apresentações/sites | D: criação/edição de documentos e artefatos por Skills/plugins; disponibilidade por superfície | Documents/uploads parciais, pipeline unificado incompleto | Tools/Skills/integrações; artefatos | Render/validação/provenance; saída sem verificação | Mapeada |
| `integrations` — Email/Calendar/Notes/Tasks/Research/Compare/Cookbook/vault/companion | O/D conforme extensão, sem equivalência por módulo | Herdadas; routes/integrations/companion | Produto/integrações; extensões | Auth/trust/tarefas; exposição excessiva/secrets | Mapeada |
| `security` — Auth/secrets/políticas/sandbox | D/O | Parcial; auth/reviewer binding/secrets/MOBS enforcement | Runtime + autoridades; segurança | Garantias verificáveis; bypass legado | Mapeada |
| `observability` — Atividade/evidência/diagnóstico | D/O | Parcial; runs/ledger/UI contextual, estimativas de contexto e duplicatas literais sem conteúdo, escopo e checklist consultivos | Runtime/produto; observabilidade | Persistência/identidade; falso sucesso/perda | Mapeada |
| `self-development` — Evoluir o próprio source separado | E | Parcial; target confiável/artifact validado/preautorização estreita | Runtime/MOBS; engenharia | TEB/Promotion/OAP; mutar executor/autoampliar | Mapeada |
| `self-audit` — Examinar código/comportamento próprios | E | Fluxo completo ausente | Specialist/evaluator; auditoria | Critérios/evidências/contexto; autoaprovação | Mapeada |
| `self-update` — Instalar/ativar nova versão | E | Ausente; Self-Development não ativa versão | Deployment/runtime; Desktop | Versão/migração/recuperação; perda de dados | Mapeada |
| `governance` — Boot/snapshot/review/mandate/OAP/provenance | E | Existente/parcial; mobs modules, ledger e TEB | MOBS mantém autoridade; consumidor implementa | Binding/estado confiável; confusão de decisões/permissões | Mapeada |
| `capability-harvest` — Evolução contínua | E | Processo documental; automação ausente | Produto/governança; fundador/maintainer | Evidence/Responsibility Harvest; descoberta virar autorização | Mapeada |

## Context Intelligence

Objetivo: disponibilizar grandes volumes de conhecimento ao runtime com contexto mínimo, relevante, verificável e economicamente eficiente. Institutional Boot já fornece roteamento mínimo por autoridade. Memória ou RAG existente não demonstra Context Engine completo.

| Fonte | Papel e fronteira |
|---|---|
| Autoridade institucional | PROJECT_INDEX e Decision Tree determinam descoberta; verificar origem/status/responsabilidade/snapshot. Similaridade não substitui autoridade |
| Corpus especializado | Conhecimento de disciplina com fontes/versão/limitações; não concede permissões nem redefine MOBS |
| Conhecimento do projeto | Código/estrutura/config/referências/defaults do target; leitura conforme mandato/baseline |
| Memória operacional | Fatos/decisões/resumos de tarefas; preservar origem/escopo/validade; não promover recordações a autoridade |

Direções arquiteturais sem implementação definitiva:

- authority-first routing;
- retrieval híbrido combinando recuperação estrutural, busca lexical e recuperação semântica/vetorial;
- reranking respeitando permissões e hierarquia das fontes;
- progressive context loading;
- hierarchical retrieval/summaries com reconstrução pelas fontes;
- cache por identidade/hash, invalidado por mudança de fonte ou autorização;
- context/token budgeting preservando invariantes obrigatórias;
- provenance de fontes/trechos recuperados, identidade e limites;
- integração futura com Model Router para contexto, modalidade, custo e capacidade.

Não estão definidos algoritmo, banco vetorial, embedding model, schema ou protocolo. RAG vetorial puro não substitui PROJECT_INDEX, Decision Tree ou autoridades oficiais. Cliente/modelo/conteúdo recuperado não ampliam mandato. Resumos/cache não dispensam evidências obrigatórias. Ranking não resolve ausência/conflito de autoridade.

## Corpus e evidências de games

Corpus futuros podem cobrir software engineering, programação/algoritmos, arquitetura, testes/debug, UI/UX, arte 2D, animação, 3D, materiais/texturas, rigging, games, áudio, audiovisual e segurança. Nenhum corpus nasce neste ciclo. Evidence Harvest e Responsibility Harvest devem demonstrar responsabilidade, fontes, reutilização, owner, consumidor e ausência de duplicação.

Corpus preserva conhecimento; Skill aplica workflow; Specialist assume papel; modelo infere; Project Profile define contexto/defaults; ferramenta executa; evaluator confronta evidências. Context Engine recupera essas fontes sem adquirir sua autoridade. Conhecimento institucional coberto é citado, não copiado. Creative Mentor e seu corpus MOBS conservam ownership de craft.

The Last Sentinel foi inspecionado em `C:\Users\fsefsefsef\Documents\last-sentinel1\last-sentinel`: projeto Godot com cenas, scripts, shaders, spritesheets e timing integrado. A inspeção de 2026-10-22 encontrou Git em HEAD `8484e2b8b2bbb5dd7ce7d1481b6b0a79d0673e27` com alterações locais, substituindo a observação antiga de commit não comprovado. Inspeção estática não certifica qualidade visual/gameplay nem baseline limpo. Idle Age é citado na referência, com evidência de projeto não acessível neste ambiente. Paths locais são localizadores da evidência consultada, não dependências runtime ou fontes portáveis já versionadas.

`C:\Users\fsefsefsef\Downloads\Animation System Codex.md` é referência fornecida pelo fundador, candidata à curadoria; sua autodescrição não cria autoridade MOBS. Princípios incluem poses, timing/spacing, peso, anticipation, arcs, follow-through, overlap, secondary motion, silhouette readability, loops, transitions e gameplay synchronization. FPS/frame budgets/escala/pivôs/pixel density/estilo pertencem ao perfil do projeto.

Geração e avaliação: intenção → referência → key poses → timing → breakdowns → in-betweens → secondary motion → integração → validação visual/gameplay. Não reduzir qualidade a frames ou smoothness. The Last Sentinel é campo de validação, não hardcode universal. Asset Forge não integra a solução de geração visual. MOBS Asset Generator conserva exports derivados.

## Evidências e atualização

Fontes locais: [Institutional Boot](../../src/mobs_institutional_boot.py), [Mandate Builder](../../src/mobs_mandate_builder.py), [Controlled Promotion](../../src/mobs_controlled_promotion.py), [TEB Windows](../../src/windows_native_execution.py), [Agent Loop](../../src/agent_loop.py), [dispatcher](../../src/tool_execution.py), [integração](../mobs-institutional-boot.md). Evidência de código não equivale a prova operacional universal.

Autoridade: MOBS PROJECT_INDEX → Decision Tree → fontes aplicáveis, incluindo Agent Runtime Integration e ARCHITECTURE_TASK_PROTOCOL §13.1–13.2. O Map não copia regras institucionais nem substitui AUTOMATION_ROADMAP. Baseline institucional acima permite localizar as fontes no repositório MOBS oficial, sem impor paths locais.

Benchmark oficial consultado em 2026-10-11: [Codex overview](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan), [Work/Codex](https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex), [Remote](https://developers.openai.com/blog/mastering-codex-remote-for-engineering), [plugins](https://developers.openai.com/plugins/concepts/plugins), [Skills](https://developers.openai.com/plugins/build/skills). Para as três classificações revisadas: [geração/edição de imagens e imagegen](https://learn.chatgpt.com/docs/image-generation), [artefatos de documentos/PDF/planilhas/apresentações](https://learn.chatgpt.com/docs/features), [extensão por Skills](https://learn.chatgpt.com/docs/build-skills) e [Game Studio Skills](https://github.com/openai/plugins/blob/main/plugins/game-studio/skills/game-studio/SKILL.md). O workflow documentado de games não certifica Godot nem o pipeline governado futuro do consumidor. Disponibilidade varia por plataforma/cliente/plano. [Computer Use API](https://developers.openai.com/api/docs/guides/tools-computer-use) não comprova disponibilidade de toda ação em todo cliente. Ferramentas/Skills observadas evidenciam extensibilidade, sem alegar core universal.

Descoberta factual → Map → priorização no Roadmap → autorização de implementação. Atualizar estado com evidência e registrar limitações/data/owner. Novas capacidades desconhecidas entram quando descobertas. Não inferir arquitetura interna do Codex nem declarar paridade universal pela cobertura da matriz.
