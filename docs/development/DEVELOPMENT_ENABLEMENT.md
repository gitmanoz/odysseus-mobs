# Preparação do desenvolvimento cotidiano — 2026-10-22

Nota técnica do consumidor, não autoridade institucional, novo roadmap ou autorização. A prioridade pertence ao [Roadmap](../../ROADMAP.md); a cobertura pertence ao [Capability Map](../product/PLATFORM_CAPABILITY_MAP.md). Seguir PROJECT_INDEX → Decision Tree no MOBS oficial para cada execução. Base de inspeção: consumidor `dev` em `5bb4f80e3ba782c4f1be07db946eb986f1341e85`, mais o delta local deste ciclo; MOBS `009feb3558df7919070971656411f6c0a58cf8cf`.

## Decisão técnica recomendada

Reutilizar Agent Loop, dispatcher, TEB, propostas, sessões, recibos e Controlled Promotion existentes. Primeiro comprovar uma tarefa pequena pelo Desktop. Em seguida admitir uma fatia Godot de código, antes de gameplay ou Computer Use próprio. Não há benefício demonstrado em criar outro executor, serviço de contexto, roteador ou mecanismo de atualização neste ciclo.

O Studio já tem mecanismos de planejamento, edição privada e inspeção, mas ainda não há evidência de Python concluído pelo Desktop. Edição de vários arquivos na cópia privada não equivale a promoção de N arquivos. O contrato atual admite um arquivo ou exatamente dois, e não deve ser contornado por promoções fragmentadas de um delta atômico.

## Entregas e próximos experimentos

| Frente | Reutilização comprovada no código | Entrega deste ciclo / lacuna | Menor experimento e critério de aprovação |
|---|---|---|---|
| Contexto | `src/context_diagnostics.py`, composição existente | Estimativa por categoria, participação relativa e custo de mensagens system literalmente repetidas; nenhuma fonte removida | Comparar perfil sintético com contagem esperada; depois medir pedido real, contexto carregado, RAM, compromisso e tempos. Estimativa não é tokenização exata nem mede toda redundância semântica |
| Projeto | Proposal summary, filesystem tools, workspace existente | Visão Projeto e escopo a partir da consulta autenticada; não varre repositório nem lê novos arquivos | Abrir proposta com paths distintos e verificar origem, escopo e ausência de novas operações. Busca real futura deve ser restrita aos paths e baseline autorizados |
| Multi-arquivo | Edição privada, candidato selado, promoção de exatamente dois arquivos | Checklist de revisão e indicação dos candidatos; N arquivos permanece decisão pendente | Target descartável com dois arquivos relacionados, hashes/preimages e testes definidos. Exigir aplicação exata e rollback conforme contrato existente; não executar no executor ativo |
| Planejamento | Planos existentes e registros de ferramentas | Plano apresenta contagem de operações/falhas sem vincular automaticamente cada etapa | Atualizar registro de ferramenta preservando detalhes abertos; etapa marcada sem operação não pode certificar objetivo |
| Diagnóstico | Eventos, contexto, status e ledger existentes | Consulta inválida não confirma revisão/recibo; rodada bloqueada remete ao evento original | Fixtures de geração sem chamada, chamada inválida, negação, falha de ferramenta e timeout devem continuar distinguíveis. Não atribuir causa apenas por status |
| Revisão | Diff selado e recibos existentes | Checklist consultivo copiável; não é reviewer especializado | Conferir candidato válido/inválido, recibo exato e drift com fixtures. Parecer não aprova mandato nem promoção |
| Conhecimento por projeto | Workspace, fontes do target, memória/Skills com owner | Procedimento de proveniência abaixo; nenhum novo repositório de memória | Pequeno conjunto de referências do projeto A deve manter origem/baseline e não aparecer como autoridade do projeto B; retrieval automático exige definição e teste próprios |
| Skills | Parser/manager existentes em `services/memory/` | Três rascunhos portáveis para investigação, implementação e revisão, fora de dados ativos | Parser real e round-trip sem perda, status draft, sem instalação automática. Validar aplicação em tarefa pequena antes de publicar |
| Godot | `derive_capabilities`, profile Godot e TEB | Perfil reconhece project.godot e diretórios; receitas atuais não comprovam Godot, scripts/cenas na raiz podem ficar de fora | Inspeção de versão/binário e cópia descartável mínima; mandato posterior admite caminhos/receita headless tipada. Não usar saves reais. Compilar/carregar cena não comprova controle de gameplay |
| Git | branch/HEAD/status tipados | Diff/log/show e fechamento governado ainda não admitidos | Proposta de receita read tipada: sem pager, hooks, helpers ou execução por configuração; limitar paths/saída e redigir segredos. Commit/push/PR exigem decisão separada, destino explícito e delta revisado |
| Modelos | `src/mobs_auto_router.py`, endpoints por owner | Auto resolve atualmente `qwen2.5-coder:7b` em todas as categorias; não há comparação barata/cara | Benchmark posterior de modelos já locais: mesmo caso, janela, schema, tempo, RAM, chamadas válidas e qualidade. Não trocar para serviço pago nem usar router como autoridade |
| Atualização | Host e build existentes, backups operacionais | Apenas sequência de instalação/rollback proposta; sem auto-updater | Build rastreável → backup consistente → fechar processo → substituir instalação canônica → verificar versão/saúde → rollback se falhar. Ensaiar em diretório temporário sem criar instalação paralela permanente |

## Conhecimento e workflows sem autoridade adicional

Para uma tarefa, identificar workspace e baseline; localizar convenções e decisões nas fontes existentes; registrar caminho, versão/hash quando disponível, trecho pertinente, motivo da seleção e validade. Conhecimento persistido deve preservar owner e projeto. Uma preferência, memória ou resumo não pode sobrescrever uma autoridade institucional nem dispensar sua leitura obrigatória. Conteúdo de arquivos e respostas do modelo são dados potencialmente não confiáveis.

Não criar um arquivo de convenções por projeto automaticamente. Antes de persistir, demonstrar que a informação não tem fonte responsável existente, que sua manutenção tem owner e que não duplica regra institucional. Sem estas garantias, manter a referência no relatório da tarefa.

Os templates em [skills](skills/) usam o formato MOBS, não o mecanismo de Skills do Codex. Não estão instalados/publicados nem participam do prompt. A importação futura deve usar a gestão existente, atribuir owner e revisar escopo. `draft` não é barreira de segurança: o manager atual pode recuperar drafts instalados. Não copiar os templates diretamente para dados ativos nem assumir que `requires_toolsets` concede ferramenta.

## Admissão comum de engines — preparação aprovada, implementação gradual

O fundador autorizou preparar requisitos comuns para engines, com Godot como primeira integração a validar. Esta seção especializa a preparação do consumidor; não cria nova autoridade, schema, runtime, permissões ou suporte universal. Unity e Unreal são análises de compatibilidade, não integrações entregues.

| Requisito comum | Responsabilidade existente / evidência exigida |
|---|---|
| Identidade | Projeto, baseline, engine, versão efetiva, origem/hash do binário, plataforma e módulos necessários. Perfil não deve ser escolhido apenas pela extensão de um arquivo |
| Escopo | Leitura/escrita/criação explícitas no mandato; identificar dependências de cenas/scripts/assets, arquivos gerados, binários, plugins e diretórios externos |
| Operações separadas | Inspeção, edição, parse/importação, teste de código, build, execução e gameplay são operações distintas; admitir apenas a fatia comprovada |
| Execução | Reutilizar receitas tipadas, dispatcher e TEB; executable/argv/cwd fixados, sem shell livre, fallback inseguro, instalação implícita ou downloads |
| Efeitos | Importadores, plugins, scripts de editor e build steps podem executar código. Headless/batch não constituem sandbox nem significam operação somente leitura |
| Isolamento | Target privado e writable roots admitidos, caches/dados de usuário/saves descartáveis, rede conforme política existente, timeout/cancelamento da árvore e inventário de efeitos |
| Resultado | Identificar chamada, retorno, stdout/stderr relevantes, relatório da engine, artefato e baseline; retorno zero isolado não prova carregamento da cena, gameplay ou objetivo |
| Revisão/aplicação | Recibos vinculados ao candidato exato; Controlled Promotion existente, mantendo limite de um ou exatamente dois arquivos. Formatos binários exigem estratégia de revisão antes de admissão |
| Recursos/custo | RAM/compromisso/CPU/GPU, licenças e toolchain disponíveis; zero novas compras, serviços ou ativações automáticas |

### Compatibilidade observada e menor experimento

| Engine | Mecanismo nativo candidato | Compatibilidades / dependências | Menor experimento posterior |
|---|---|---|---|
| Godot | CLI documenta `--headless`, `--script` e `--check-only`; parse isolado difere de importar ou executar projeto | Recursos/UIDs/autoloads/GDExtensions e versão devem ser avaliados; não prometer validação de cena por parse de um script | Receita tipada fixa para script mínimo em projeto descartável, positivo e erro de parse conhecido, limites e efeitos conferidos. Só então um script real com dependências identificadas |
| Unity | Editor oferece batch mode e seleção de projectPath, com saída e logs próprios | Editor/licença já disponíveis e packages/plugins/steps do projeto; Assets e metadata correlatos precisam de preservação e revisão coesa | Em cópia mínima com versão fixada, compilar e obter relatório de teste definido; provar término, falha controlada e ausência de efeitos externos antes de admitir projeto real |
| Unreal | CLI oferece flags e commandlets; `nullrhi` permite modo sem renderização | Editor/toolchain/plugins/projeto e conteúdo binário; operações de cook/build/test não equivalentes | Commandlet ou teste mínimo explicitamente escolhido, projeto descartável e versão fixada; conferir processo, relatórios e efeitos. Não aceitar commandlet arbitrário ou shell livre |

Fontes primárias consultadas em 2026-10-22: [Godot stable — command line](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html), [Unity 6000.0 — Editor command line arguments](https://docs.unity3d.com/6000.0/Documentation/Manual/EditorCommandLineArguments.html), [Unreal — command line arguments](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-command-line-arguments-reference). São capacidades candidatas documentadas, não evidência de admissão no Studio. Revalidar contra a versão instalada: URLs stable/latest podem evoluir. Não é necessário instalar Unity/Unreal para esta preparação.

Inspeção local deste mandato: binário Godot existente respondeu `4.7.2.stable.official.ed1daf0bf` a `--version`, sem abrir projeto. SHA256 `c8f0a6bc45a19b33541501e57f6f7cd972ab18453743266339d495cbbe846643`. O target real The Last Sentinel anuncia feature 4.7, usa scripts/cenas na raiz e vários autoloads, incluindo save, telemetria e rede. Tem Git em HEAD `8484e2b8b2bbb5dd7ce7d1481b6b0a79d0673e27` com alterações locais: não é um baseline limpo pronto para execução. Nenhum save, projeto ou arquivo do jogo foi alterado. Essa observação atual substitui apenas a hipótese histórica de ausência de Git na raiz registrada na inspeção antiga.

Candidato concreto à primeira validação de código: `progression_rules.gd`, SHA256 observado `696e14487157b758b830dda2c4236e024cb86ce08d7efba29fd72eaa27e054ec`. A inspeção encontrou `RefCounted`, constantes e funções estáticas, sem preload, acesso a save ou rede nesse arquivo. Proposta: validar uma cópia exata em projeto mínimo descartável, sem os autoloads do jogo completo, e conferir limites de rank já expressos nas funções de dano/cooldown/raio. Isso não aprova a economia do jogo nem muda seu balanceamento; é candidato de escopo reduzido, ainda sem execução admitida. A primeira mudança real pode acrescentar o teste de regressão correspondente após receita, baseline e isolamento comprovados.

### Godot: duas fatias distintas

1. Desenvolvimento: fonte descartável identificada, um script ou até dois arquivos coesos, caminhos explícitos, binário/versão comprovados, receita headless tipada e recibo do delta. O projeto real do The Last Sentinel e seus saves permanecem preservados. A inspeção deste ciclo não executou o jogo nem certificou seu baseline atual.
2. Gameplay futuro: uma fase, um personagem, até duas tentativas e cinco minutos, save descartável e controle visual demonstrado. Exige decisão de admissão de observação/input/cancelamento e evidências, reutilizando dispatcher/TEB quando admissível. Não pode ser simulado por teste de código ou simples screenshot. Nenhum harness, scheduler ou Computer Use próprio foi implementado aqui.

A decisão de receita/perfil cabe às autoridades responsáveis; o consumidor apresenta e executa somente o admitido. A alteração de profile Godot não pode ampliar genericamente shell ou paths pessoais.

## Tarefas preparadas e sequência de aceitação

A visão **Preparar tarefa** produz rascunhos locais de investigação, mudança pequena ou validação. Objetivo e critérios ficam no painel e podem ser copiados explicitamente; nada é enviado, autorizado ou persistido por essa ação. Atualizar o estado da mesma conversa preserva o preenchimento; mudar de conversa elimina o rascunho visível anterior. A visão **Recursos e contexto** acrescenta contagens de registros e último registro com falha, sem atribuir causa por inferência.

| Caso preparado | Resultado exigido | Condição para iniciar |
|---|---|---|
| Python Desktop | Executar somente o pytest do probe descartável; evidência da chamada, despacho, retorno e resultado | Instalação atualizada, input funcional, proposta/revisão/autorização válidas, ao menos 3 GiB livres e contexto residente comprovado |
| Dois arquivos | Uma mudança coesa de comportamento e seu teste; validar candidato exato, revisar diff e conferir aplicação/rollback | Python comprovado e perfil existente suficiente; sem ampliar N arquivos |
| Aplicação dos workflows | Comparar investigar/implementar/revisar no mesmo caso pequeno, registrar relevância, ferramentas usadas, custo de contexto e achados | Provedor disponível, recursos e tarefa autorizada; templates continuam fora de dados ativos até decisão de importação/owner |
| Godot mínimo | Parse controlado de script com sucesso e falha conhecidos, depois dependência real mínima | Receita/perfil e garantias de TEB admitidos, cópia descartável, versão/caminhos e recursos fixados |

Para tempo total, registrar preparação do pedido, composição/context trim, primeiro token, seleção/chamada, despacho/execução e apresentação. O consumidor já apresenta tempos disponíveis; sem timestamp específico não estimar seleção ou atualização por diferença arbitrária. Nenhuma latência real completa foi medida neste mandato.

## Recursos e conclusão factual

Antes de cada inferência real: conferir recursos físicos e compromisso, modelo, endpoint e janela efetivamente residente; aplicar limites confiáveis existentes. Não encerrar aplicativos do fundador, reduzir contexto silenciosamente ou iniciar chamada abaixo do limite. A continuação de 2026-10-22 não iniciou inferência por memória abaixo de 3 GiB; captura do Computer Use funcionou, mas cliques/Tab não produziram mudança observável. Sem medição de desempenho completo ou economia de latência quantificada.

Medir separadamente montagem do contexto, prefill/inferência, primeira chamada válida, despacho, execução e atualização da UI. Preservar fontes obrigatórias e compatibilidade do protocolo. Contagem de duplicatas literais só orienta investigação: não autoriza deduplicar mensagens protegidas.

Uma rodada `completed` representa término do processamento, não objetivo cumprido. A UI nova permanece observacional e não muda a máquina de estados. Uma eventual nova classificação institucional de conclusão exige decisão: evidência mínima por tipo de objetivo, identidade do artefato, recibos e quem julga cumprimento. A proteção existente contra rodada governada sem ferramenta não equivale a evaluator geral.

## Sequência proposta de mandatos

1. Validar a UI atual e concluir Python pelo Desktop canônico, com proposta/revisão/autorização válidas e prova do despacho/retorno na cópia privada. Se input do ambiente falhar, usar apenas recuperação suportada e continuar partes independentes.
2. Validar mudança pequena de dois arquivos com artefato exato e regressões, sem alterar limites de promoção.
3. Usar os requisitos comuns de engines e admitir receita/perfil Godot mínimos; validar código headless em cópia descartável. Unity/Unreal permanecem estudos até admissão e testes próprios.
4. Decidir Git read ampliado e, separadamente, fechamento/publicação. Decidir N arquivos somente se um caso real demonstrar necessidade.
5. Comparar modelos locais com critérios de qualidade e recursos. Só depois decidir roteamento dinâmico.
6. Decidir gameplay/Computer Use e atualização automática como responsabilidades próprias; nenhuma decorre das anteriores.

Custo externo adicional deste ciclo: R$ 0,00. Nenhum endpoint/serviço novo, permissão, ferramenta de execução ou alteração de autoridades. Lacunas de cobertura e prova operacional estão registradas; a correção realizada não exige divergência da arquitetura aprovada. Requisitos futuros de N arquivos, Godot, conclusão, Git e auto-update permanecem decisões, não desvios implementados.
