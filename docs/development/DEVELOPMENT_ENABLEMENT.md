# Preparação do desenvolvimento cotidiano — atualização 2026-10-24

Em 2026-10-23, o Desktop executou `python -m pytest -q tests/test_probe.py` pela
TEB (`windows_appcontainer_job_v1`), com retorno 0 e target original intacto,
sem promoção. A rodada ficou `blocked` na chamada posterior por excesso de
contexto. Isso comprova a operação Python, mas não o ciclo completo com síntese.
A prova local está em C:/AI/STUDIO_PYTHON_DESKTOP_RESULTADO.md; nenhum dado de
conta, autorização ou recibo pessoal deve ser incorporado ao repositório.

O consumidor corrige o desconto duplo de tokens protegidos e o transporte da
aprovação sem texto. O flag de shell do rascunho comum não acompanha essa
aprovação; o servidor continua verificando privilégios, recusas explícitas,
mandato e TEB. Não há alteração de permissão persistente ou autoridade.

Na rodada de 2026-10-24, o orçamento inicial reserva também 512 tokens mínimos
para uma chamada curta e seu retorno. O preset opcional pode ser reduzido com
aviso antes de cortar o pedido, enquanto autoridades/protocolo protegidos
permanecem literais. Um retorno grande ou várias chamadas ainda podem exceder
a janela e continuam bloqueados; essa reserva não promete execução ilimitada.
O feedback do comando mantém saída e código, com digest do recibo integral
preservado no ledger. Um bloqueio posterior passa resultados observados e
diagnóstico parcial ao salvamento existente do histórico, sem marcar sucesso.

As regressões sem modelo cobrem preservação, negações, orçamento de duas rodadas
e evidência parcial pelo caminho HTTP. A repetição no Desktop desta rodada
depende de login manual: a tela de autenticação não é automatizada. Não foi
certificado um novo ciclo completo, teste negativo ou edição/promoção por UI.

Nota técnica do consumidor, não autoridade institucional, novo roadmap ou autorização. A prioridade pertence ao [Roadmap](../../ROADMAP.md); a cobertura pertence ao [Capability Map](../product/PLATFORM_CAPABILITY_MAP.md). Trabalho comum usa código, testes e requisitos locais; decisões institucionais e execuções governadas seguem `PROJECT_INDEX.md` → Decision Tree no MOBS oficial. Baseline deste ciclo: consumidor `dev` em `d2a7312d44966452c9f8dfff61ec0444178224db`, mais as correções descritas; MOBS `009feb3558df7919070971656411f6c0a58cf8cf`, somente leitura.

## Decisão técnica recomendada

Reutilizar Agent Loop, dispatcher, TEB, propostas, sessões, recibos e Controlled Promotion existentes. Primeiro comprovar uma tarefa pequena pelo Desktop. Em seguida admitir uma fatia Godot de código, antes de gameplay ou Computer Use próprio. Não há benefício demonstrado em criar outro executor, serviço de contexto, roteador ou mecanismo de atualização neste ciclo.

O Studio já tem mecanismos de planejamento, edição privada e inspeção, e uma operação Python real comprovada pelo Desktop. O ciclo completo e repetível com síntese continua pendente. Edição de vários arquivos na cópia privada não equivale a promoção de N arquivos. O contrato atual admite um arquivo ou exatamente dois, e não deve ser contornado por promoções fragmentadas de um delta atômico.

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

## Continuação de qualidade sem Computer Use

Base desta continuação: `25c5631f308887efe066216aa81405e59b52e441`. Nenhuma inferência, teste gráfico ou execução de projeto Godot. A continuidade foi confrontada por persistência real em SQLite temporário, requisições sintéticas distintas, desconexão/reconexão e substituição de rodada aguardando o salvamento parcial. Os casos preservam último pedido, ordem e isolamento entre sessões. Isso não demonstra a causa da saudação repetida pelo modelo real; nenhuma mudança artificial de prompt foi introduzida para mascará-la.

Chamadas nativas malformadas agora são rejeitadas isoladamente; não podem disparar exemplos por fallback textual. Os schemas existentes das ferramentas de código fornecem tipos e campos obrigatórios para a conversão. Valores vazios explícitos continuam válidos quando o contrato permite, por exemplo criação de arquivo vazio ou replacement vazio. Aliases existentes de patch continuam aceitos; entradas rejeitadas não concedem permissão nem mudam o dispatcher. Negação por ferramenta desabilitada ou política é testada antes da execução vinculada.

### Medição de overhead e limite da otimização

Um caso real da suíte multifile isolada levou 45,08 s na chamada, com 29 capturas de repositório, 58 fingerprints de metadados e 697 invocações Git. Consulta conjunta dos mesmos quatro caminhos de metadados reduziu as invocações para 523, mantendo as 29 capturas e os 58 fingerprints; a chamada levou 33,01 s no ensaio posterior. A melhora observada é de aproximadamente 27% nesse caso; não extrapolar para toda a suíte, para modelo ou para Computer Use. Perfis cProfile incluem overhead e as medições não são benchmark estatístico de múltiplas máquinas.

Não foram removidos hashes, leitura de index/config/HEAD/config.worktree, comparação antes/depois, verificações de reparse/drift/alternates ou ambiente Git restrito. Testes com repositório normal e worktree confrontam o mesmo fingerprint com as quatro consultas anteriores. Saída incompleta/ambígua falha fechada. Uma alternativa de redirecionar pipes para arquivos temporários não melhorou a mediana no ensaio intercalado e foi descartada, sem alteração de produção.

### Exemplos concretos para os workflows

| Workflow | Caso e definição utilizável | Evidência / limite |
|---|---|---|
| Investigar defeito | Reproduzir chamada nativa com `write_file` sem conteúdo, envelope não-objeto ou ferramenta desconhecida junto a exemplo textual. Esperado: rejeição sem crash, despacho ou execução do exemplo | Casos sintéticos em `test_native_tool_contract.py`; o defeito foi corrigido nesta continuação, não repetir como pendência aberta |
| Implementar mudança pequena | Acrescentar regressão que preserve o último pedido ao reabrir conversa e impeça mistura entre sessões. Esperado: histórico original e novo pedido no contexto, replay sem duplicação e preservação do salvamento parcial | Exemplo implementado em `test_session_continuity_offline.py`; não substitui teste com modelo real |
| Revisar delta | Examinar o candidato de dois arquivos e confrontar digest, paths, recibo e drift por rename/criação concorrente. Esperado: mudança do usuário preservada, aplicação bloqueada e nenhum sucesso presumido | Testes em fixtures; a visão Revisão da tarefa apresenta digest e arquivos, mas não cria recibo ou aprovação |

### Especificação mínima proposta da receita Godot

Preparação, sem admissão operacional. Binário/versão/hash são os já identificados; o próximo mandato deve declarar a pinagem admitida ao executor existente e comprovar bibliotecas/diretórios necessários sem liberar caminhos gerais. Perfil deve permitir apenas manifest e scripts de teste explicitamente escolhidos, incluindo arquivos na raiz quando pertinentes. A receita de parse candidata usa argv fixo `--headless --path <cópia privada> --check-only --script <script autorizado>`; rejeitar flags extras e caminhos fora do target. A documentação da versão e o próprio binário devem confirmar os argumentos antes da admissão.

Preparar um baseline mínimo descartável, com manifest sem autoloads/plugins/GDExtensions do jogo real, script positivo e erro conhecido. Primeiro comprovar ambos os resultados e inventário, sem saves, rede, imports arbitrários ou criação de APK. Verificar também a aceitação de scripts RefCounted em check-only nessa versão; se exigir outra forma de invocação, devolver a diferença à decisão da receita, sem inventar um harness ou executar o projeto inteiro. Só depois avaliar `progression_rules.gd` e um teste de limites já existentes, sem reequilibrar o jogo.

Comandos de parse, teste lógico, importação, build e gameplay permanecem operações distintas. Timeout, cancelamento da árvore, logs limitados, isolamento de user-data/cache e limite de recursos precisam de prova no dispatcher/TEB atuais. Leitura da CLI e um retorno zero não bastam. A promoção segue em um ou exatamente dois arquivos; manifest de fixture deve existir no baseline, não ser uma terceira alteração implicitamente promovida.

### Preparação da próxima ativação

Preflight somente leitura encontrou as dependências Desktop pinadas presentes e sem requisitos quebrados, além do CAB WebView2 existente com SHA256 esperado. A instalação canônica conserva a versão 1.0.2; difere do source em módulos de protocolo/metadados/contexto e recursos web, e ainda não contém studioEngineering.js. É necessário rebuild para ativar o conjunto completo.

O script de build atual instala requisitos e remove build/dist antes de empacotar. Não executá-lo contra o aplicativo aberto. Próxima ativação: confirmar fechamento normal e recursos; manter backup binário completo e dados/config; produzir build rastreável em staging temporário dentro da infraestrutura de build, verificar inventário/version/hash/toolchain/WebView2; substituir somente a instalação canônica liberada; conferir saúde e versão, com rollback para o backup se necessário. Não criar instalação permanente paralela, atualizar dependências silenciosamente ou apagar evidências. Nenhuma dessas etapas foi executada nesta continuação.

## Streaming, cancelamento e preparação segura — continuação offline

Base: `aedcd28f16bc1a4ba685e4003d54676b47fb1598`. Fixtures de transporte exercitam o parser real, com fragmentos, chamadas paralelas, argumentos incompletos, tipos inválidos, timeout e erro de rede. No caminho compatível OpenAI, uma entrada inválida não pode descartar chamadas irmãs; continuação inválida identificada pelo índice invalida aquela chamada inteira. No nativo Ollama, argumentos não-objeto não viram `{}` e EOF sem o marcador `done` produz erro de transporte sem liberar ferramentas pendentes. O compatível OpenAI mantém sua tolerância existente a EOF sem `[DONE]`; não é uma certificação de todos os protocolos ou gateways.

Cancelamento anterior ao primeiro tick agora fecha a fonte sem iterá-la. Cancelar durante espera pelo salvamento anterior também encerra corretamente; uma substituição cancelada mantém a barreira de salvamento para o terceiro envio. Repetir Parar não cancela o cleanup já iniciado. Esses estados pertencem ao gerenciador de transporte; não alteram a máquina de estados institucional nem significam objetivo cumprido. Testes sintéticos não comprovam término de toda árvore de processos de ferramentas reais.

A camada pública do Agent Loop fecha explicitamente seu gerador interno: fechar a transmissão aguarda o cancelamento da tarefa de ferramenta, em vez de depender do encerramento posterior do event loop. A conversão também rejeita argumentos não-objeto para ferramentas de código com todos os campos opcionais; `[]`, `false`, `0` ou `null` não viram uma leitura padrão de diretório/workspace. O objeto `{}` explicitamente válido continua obedecendo ao schema e às mesmas permissões.

A inspeção e testes offline não encontraram reutilização de respostas prontas no streaming: esse caminho não consulta o cache de respostas de `llm_call`/`llm_call_async`, e pedidos diferentes chegam ao transporte sintético. A chave desse cache inclui mensagens e histórico. Isso não elimina hipóteses no modelo, KV-cache do servidor, parâmetros ou contexto real; a causa das saudações repetidas continua aberta até inferência rastreada. Nenhum prompt corretivo artificial foi acrescentado.

O build existente agora oferece `-CheckOnly`: verifica requisitos instalados e suas restrições, consistência de dependências e CAB WebView2 pinado, sem criar venv, instalar, baixar, extrair, limpar outputs ou empacotar. O build normal preserva seu comportamento de instalação de requisitos, mas recusa o executável canônico aberto antes de instalar e novamente antes de limpar; não encerra processos. Recusa também destinos build/dist ligados, links internos ou inventário ilegível. Isso reduz risco, mas não elimina a corrida com uma abertura posterior: ativação continua exigindo fechamento e backup. Staging/rollback são preparação documental, não uma nova instalação ou um atualizador automático.

A revisão apresenta a sequência solicitação → autorização → chamada → despacho → retorno → validação, com origem e lacunas explícitas. Revisão de snapshot não é autorização; aprovação registrada não comprova execução. Os resumos visuais não inventam recibos de chamada/despacho nem certificam cumprimento.

### Godot: matriz do menor experimento proposto

Não admitido nem executado neste ciclo. Primeiro definir o fixture e seus digests no mandato, em cópia privada; reaproveitar dispatcher/TEB e o binário já identificado, sem inserir outro executor. O conjunto abaixo é especificação de teste futuro, não profile operacional.

| Dimensão | Entrada / condição fixada | Resultado exigido |
|---|---|---|
| Arquivos | `project.godot` mínimo, sem autoloads, plugins, GDExtensions ou cenas do jogo; um `probe.gd` com `extends RefCounted` e função estática retornando uma constante | Inventário/hashes antes e depois; nenhum acesso a projeto real ou saves |
| Positivo | Receita candidata `--headless --path <cópia privada> --check-only --script res://probe.gd` | Confirmar suporte da versão pinada e recibo atribuível ao processo; sucesso de parse não prova teste lógico |
| Negativo | Mesmo fixture/digest identificado, com erro sintático deliberado no script | Retorno não zero e diagnóstico limitado; não considerar falha esperada um sucesso do objetivo de produção |
| Confinamento | `../`, caminho absoluto externo, script não listado e flags extras | Rejeição pelo dispatcher antes de iniciar processo |
| Efeitos | User-data/cache temporários confinados, rede/filhos/bibliotecas sob limites existentes comprovados | Nenhum save real, efeito externo ou download; se o executor não oferecer garantias, bloquear a admissão |
| Interrupção | Limite de tempo/recursos e cancelamento definidos antes da execução | Recibo factual de interrupção e término da árvore; não simular timeout com mera mensagem |

Depois do parse positivo/negativo e confinamento, avaliar a dependência mínima real de `progression_rules.gd`. Teste lógico, importação, build e gameplay exigem receitas distintas. Nenhuma ampliação para Unity/Unreal, N arquivos ou controle de jogo decorre desta preparação. A decisão pendente deve especificar a receita/perfil exatos e as capacidades de isolamento comprováveis; sem isso, não iniciar o experimento.

## Consolidação offline e gates de prontidão

O mandato seguinte consolida o delta local sobre `aedcd28f16bc1a4ba685e4003d54676b47fb1598`, sem Computer Use, inferência ou ativação. Os estados abaixo são critérios de aceitação do consumidor e complementam o [Capability Map](../product/PLATFORM_CAPABILITY_MAP.md); não constituem outro roadmap ou autoridade de admissão.

| Capacidade | Prontidão observável | Gate restante para desenvolvimento cotidiano |
|---|---|---|
| Planejamento e preparação | Implementados rascunhos locais, planos e checklist; DOM exercitado sem envio/execução | Confrontar utilidade e cumprimento em tarefa real, sem tratar plano marcado como prova |
| Composição da conversa | Persistência/replay e histórico exercitados offline; pedidos sintéticos preservados | Investigar repetição com contexto e geração reais; não há causa comprovada para a saudação repetida |
| Chamadas de ferramentas | Parser/conversor exercitados com fragmentos, IDs conflitantes, tipos inválidos e interrupção | Demonstrar chamada do modelo, despacho e resultado na instalação canônica |
| Cancelamento e salvamento | Camadas fecham geradores/tarefas; parada repetida e substituição preservam ordem; falha de persistência fica explícita na rota HTTP | Comprovar comportamento com processo/ferramenta real e reabertura no Desktop |
| Edição privada e promoção | Um ou exatamente dois create/write admitidos; revisão/recibo vinculados ao candidato exato e rollback possuem regressões | Python E2E primeiro; depois caso real coeso de dois arquivos. N arquivos arbitrários continua fora da admissão |
| Apresentação de evidências | Escopo, revisão, atividade, recursos e guia de falhas implementados sem conceder autorização | Inspeção visual no build atualizado e conferência da cadeia de uma operação real |
| Atualização | Preflight offline e gates de build exercitados; instalação existente preservada | Backup consistente, build rastreável, ativação e rollback operacional ainda não realizados neste ciclo |
| Godot / outros motores | Matriz de experimento mínimo preparada; nenhuma nova receita operacional | Decisão e prova de confinamento da receita Godot; Unity/Unreal exigem estudos/admissão próprios |
| Computer Use / gameplay | Ausente como capacidade própria governada do Studio | Mandato arquitetural e admissão de observação/input/verificação; nenhuma execução de jogo neste ciclo |

### Identidade, encerramento e salvamento

IDs de chamada devem ser strings quando presentes. No compatível OpenAI, ID repetido em slots diferentes, mudança de ID ou nome no mesmo slot tornam as chamadas envolvidas não executáveis. Continuação sem índice mas com ID conhecido usa esse ID em vez da última chamada paralela. No nativo Ollama, IDs repetidos também são rejeitados. Chamadas iguais sem ID não são deduplicadas por conteúdo: podem representar operações legitimamente distintas. Essas garantias não implementam idempotência geral entre rodadas ou reinícios.

A tolerância histórica do compatível OpenAI a EOF foi estreitada para chamadas pendentes: só são liberadas com `[DONE]` ou finish_reason terminal aceito (`stop`, `tool_calls`, `function_call`). `length`/`content_filter` não liberam chamadas mesmo com `[DONE]`. Texto sem ferramenta mantém compatibilidade anterior. Timeout/erro de rede preserva o parcial e não libera chamadas pendentes. Nenhum texto de promessa vira evidência de despacho.

Falha ao salvar uma resposta interrompida no modo agente era absorvida, deixando apenas o estado de parada. Agora a falha sobe ao gerenciador como erro; finally ainda limpa o registro ativo e a resposta HTTP usa mensagem genérica, sem detalhes do armazenamento. Falha ao fechar a fonte também é observável como erro. Isso não inventa retry automático nem garante restauração de gravação que falhou; o replay é em memória e não sobrevive ao restart.

### Thinking e interpretação das falhas

O commit `cce11abe26fbb7a672cc64cd01aad137fb9ee5cf` ampliou deliberadamente `think:false` a todo endpoint Ollama compatível, sem depender do nome do modelo. O teste antigo contradizia essa política; foi alinhado e os comentários corrigidos, sem alterar parâmetros de geração. Endpoints OpenAI remotos continuam sem essa injeção. Nenhuma configuração de contexto/modelo foi mudada.

O diagnóstico oferece orientação para distinguir provedor/transporte, formato, autorização e execução pelas fontes originais. O formato atual dos registros não permite inferir todas essas causas de um código de saída; não foi criado classificador por palavras na saída, nem nova autoridade ou contrato de estado.

### Preparação de ativação e consolidação

Preservar instalação inteira (exe e `_internal`, inclusive WebView2 e toolchain), configuração externa e dados efetivos do usuário. O default congelado é `~/.odysseus/data`, mas override de ambiente deve ser revalidado antes de backup. SQLite ativo exige backup consistente ou fechamento confirmado, não cópia isolada do arquivo principal ignorando WAL. O backup inicial deste ciclo cobre fontes/diff locais; não equivale a backup consistente dos dados do aplicativo.

O preflight não prova que o novo pacote foi construído ou ativado. A preparação registra dependências, CAB e inventário do pacote atual; ativação continua separada. A lista autorizada pede preparar commit/push: delta revisado, mensagens e proposta de changelog devem ficar concretos antes da publicação. HISTORY é avaliado separadamente; não transformar cada regressão em marco institucional.

## Itens locais do roadmap: exploração, revisão e ensaios

O ciclo seguinte autoriza publicar a consolidação e executar somente os itens marcados Local. A exploração reaproveita os retornos de `read_file` e o preview autenticado existente, sem criar API de leitura geral. A visão **Fontes carregadas** organiza as pastas observadas, procura texto literal com até 100 resultados e abre o trecho por linha. É um índice de snapshots da conversa, não a árvore completa do disco nem um indexador semântico. Arquivos ainda não lidos continuam exigindo uma tarefa/leitura admitida. Escopo e exclusões continuam em **Projeto e escopo**.

Leituras bem-sucedidas passam a registrar caminho solicitado e linha inicial; o Agent Loop acrescenta workspace e baseline do mandato quando disponíveis. O baseline é referência da autorização, não hash do arquivo atual. O conteúdo mostrado pode já ter sido limitado pelo executor; o painel mostra até 40 linhas por posição e limita a captura adicional a 64 KiB. Não reconstrói origem de registros antigos. Mudar sessão/workspace elimina a visão anterior; controles destacados e respostas atrasadas não devem consultar outro projeto. A busca só opera sobre texto carregado, nunca envia código ou consulta externa.

O preview do mesmo candidato pode mostrar todos os arquivos juntos ou um por vez, mantendo comparação antes/depois/diff e cópia dos bytes recebidos, inclusive CRLF e arquivo vazio. O digest do conjunto fica explícito. Copiar não valida ou aplica; referência obsoleta bloqueia controles. O checklist continua reunindo escopo, recibo exato e limites. O catálogo de receitas explica pytest, py_compile e Ruff sem confundir compilação/lint com teste funcional; receitas desconhecidas não recebem interpretação inventada.

Diagnóstico de contexto acrescenta contagem/custo estimado de schemas por família fechada. O ensaio offline compara os 71 schemas consumidores com os conjuntos de leitura (5) e desenvolvimento (9) já existentes: aproximadamente 17.688, 767 e 1.449 tokens de schemas, respectivamente, pela mesma heurística. Mensagens e autoridades são idênticas em cada comparação. Isso não demonstra que os 71 schemas foram enviados na tentativa histórica de 28 mil tokens, não mede prefill/memória e não muda a seleção do runtime. MCP, protocolos textuais e filtros por autorização continuam separados. Histórico de 2, 40 e 300 mensagens permite confrontar crescimento sem inferência ou remoção de fontes protegidas.

O build existente agora captura hashes dos fontes Python/recursos Git-visíveis antes do empacotamento e os reconfere depois. O manifesto final inventaria bytes/hashes do pacote, incluindo toolchain e WebView2; ausência de componentes obrigatórios, mudança do source ou divergência do inventário impede aceitação pelo verificador. É evidência de integridade relativa a um manifesto confiável, não assinatura de origem, garantia de build reproduzível ou teste de boot. Nenhum pacote novo foi construído/ativado neste ciclo. O CLI de backup existente foi ensaiado somente em SQLite WAL e configuração descartáveis; snapshot, verify, restore e integrity_check preservaram os dados esperados e a cópia de segurança da restauração.

### Casos concretos de autodesenvolvimento para replay futuro

Os defeitos abaixo já estão corrigidos no consumidor atual. Servem como casos pequenos e reproduzíveis em target descartável separado no baseline indicado; não são pendências de produção nem autorizam criar esse target automaticamente. A nova proposta deve identificar os dois roots, baseline, paths, revisão e autorização válidas. Não reaproveitar aprovações antigas nem alterar o runtime ativo.

| Caso | Baseline do target de reprodução | Delta máximo / aceitação |
|---|---|---|
| Cancelamento antes do primeiro tick | `aedcd28f16bc1a4ba685e4003d54676b47fb1598` | `src/agent_runs.py` e teste de regressão em tests; estado terminal e fonte fechada sem iniciar ferramenta |
| Argumentos não-objeto viram leitura padrão | `aedcd28f16bc1a4ba685e4003d54676b47fb1598` | `src/tool_schemas.py` e teste; rejeitar arrays/bools/números sem rejeitar `{}` válido |
| Origem da leitura por faixa | `9dd9a4dcf06cd586f6253874d02f941dc93b8aa6` | `src/agent_tools/filesystem_tools.py` e teste; linha/caminho correspondem ao trecho e falha não fabrica origem |

### Avaliação preparada dos workflows existentes

[workflow-evaluation.json](workflow-evaluation.json) fixa um mesmo projeto sintético de dois arquivos para investigar, implementar e revisar. `average([])` provoca divisão por zero; o candidato correto preserva média de entradas positivas/negativas; um candidato que usa max passa o vazio e falha nos dois casos não-vazios. O probe offline confronta essas três variantes com os mesmos testes/interpretador. Isso valida a discriminação do fixture, não a qualidade de um modelo nem a execução pelo Studio. Templates continuam draft, sem instalação/ativação automática, novo harness de gameplay ou autoridade.

### Consolidação do checkout legado e instalação única

O checkout ativo é odysseus-mobs-dev, branch dev. O checkout primário
odysseus-mobs, branch agent/mount-mobs-workspace @ 871db18, compartilha
os metadados Git com ele e contém delta local: não é descartável nem deve
receber novas implementações. A revisão do legado reaproveita paginação de
read_file, com proveniência mantida e aviso para linha parcialmente lida;
retira o fade artificial por token do renderer e reconhece pedidos explícitos
de inspeção em português, sem transformar a classificação em autorização.

Não são importados o dispatch determinístico baseado em prosa, os marcadores
invisíveis para escolhas nem o supervisor legado com retries automáticos. Eles
não substituem chamada válida do modelo, dispatcher/TEB e evidência atuais.
O overlay Docker e suas variáveis/docs eram configuração de deployment opcional
anterior; não são necessários para a instalação nativa e não são ativados como
outro runtime. O workflow temporário de aplicar patches foi removido na própria
branch antiga; não há razão para recriá-lo. Conteúdo legado fica preservado,
sem merge cego e sem declarar todos os seus comportamentos admitidos.

Atualizações Desktop usam o mesmo caminho canônico e o atalho existente, sem
clones, instalações paralelas ou backups completos automáticos. Git preserva
o código e dados/configuração continuam fora do pacote. O build oferece
-UseExistingDependencies: valida venv/requisitos/pip check/CAB primeiro e
reutiliza esses componentes sem instalar ou baixar outros. A ausência deles
bloqueia esse modo antes de limpar outputs. Backend congelado ainda requer
rebuild/reinício normal. As recomendações históricas acima de backup completo
por ativação não são o procedimento atual; a diretriz do fundador de instalação
única prevalece. Isolamento privado obrigatório da TEB permanece inalterado.

### Incremento offline de desenvolvimento — 2026-10-23

Este incremento implementa os itens 1–24 do lote aprovado, sem Computer Use,
inferência ou novas instalações. A instalação permanece no checkpoint 79447c9:
o build deste incremento não foi iniciado por insuficiência de espaço no C:.
Os testes offline não certificam interação gráfica ou geração de ferramentas.

| Superfície | Incremento no source | Limite factual |
|---|---|---|
| Identidade e atualização | Identificação pública reduzida do manifesto; comparação opcional com source/HEAD; erros de integridade por componente; reserva de disco antes da limpeza; shell web network-first e fallback apenas no cache corrente | Identificação não é verificação criptográfica de origem nem prova de boot; nenhum novo pacote ativado |
| Leituras observadas | Metadados de paginação vivos/persistidos; leitura de até 20 mil caracteres preservada na apresentação; estados incompleto/EOF/desconhecido; agrupamento e conflitos entre páginas; filtro, cópia de trecho/referência e navegação ao evento | Somente snapshots carregados; continuação é texto copiável, nunca envio automático; registros antigos não ganham completude presumida |
| Revisão selada | Diferenças de espaços/newlines, páginas de 200 linhas, resumo agregado e notas vinculadas ao arquivo/digest | Paginação só visual; cópia integral preservada; notas consultivas não aprovam nem alteram candidato |
| Preparação | Salvar/restaurar explicitamente rascunhos por conversa/workspace nas preferências existentes, isoladas por conta; critérios com referências consultivas | Substitui a descrição anterior de rascunhos apenas em memória; nenhuma submissão ou autorização automática |
| Diagnóstico | Links de arquivo/linha somente para fonte já carregada e caminho conhecido; tempos observados de preparação, stream, gates e handler; exportação reduzida por campos permitidos | Caminhos absolutos/relativos divergentes podem não gerar link; handler não prova efeito externo; stream inclui processamento e não isola tempo de GPU |

As regressões abrangem paginação, contexto de workspace, controles obsoletos,
formatos antigos/malformados, isolamento de contas, bytes selados, cache e gates
de build. Logs/JUnit locais: `C:/AI/studio-offline-batch-*.log/xml`.
O relatório consolidado é `C:/AI/STUDIO_OFFLINE_BATCH_30.md`.

Os itens 25–30 estão em [decisões offline](OFFLINE_DEVELOPMENT_DECISIONS.md).
São propostas não aprovadas para Git tipado, fechamento, promoção N-arquivos,
validação Godot e conclusão factual. Não concedem ferramentas nem mudam estados.
HISTORY foi avaliado separadamente: nenhum marco institucional novo; não criar
arquivo no consumidor nem editar o HISTORY do MOBS para registrar este delta.

### Refinamento das fontes e atualização canônica — 2026-10-23

O relato de falta de disco acima descreve o fechamento anterior. Após recursos
liberados, o mandato seguinte autoriza recompilar no mesmo caminho. O resultado
do build e a identidade efetivamente instalada são registrados no manifesto e
em `C:/AI/STUDIO_NEXT_OFFLINE_BATCH.md`, sem inferir instalação a partir do Git.

O painel agora mostra intervalos de linhas completas observadas e lacunas
internas, sem certificar leitura integral ou atualidade. A comparação inclui
linha final completa, ignora caudas incertas e limita pares/linhas examinadas.
Hashes persistidos são revalidados; arquivo vazio não gera linha/cópia fictícia.
CRLF é apresentado sem CR residual, mantendo texto recebido para cópia.
Continuação não é oferecida se puder saltar conteúdo cortado na apresentação.

Rascunhos permitem limpar explicitamente o valor salvo nas preferências
existentes (null), preservando o texto local. Botões de persistência bloqueiam
requisições concorrentes; mudança de escopo torna controles antigos inertes.
O diagnóstico reduzido inclui apenas totais/contagens finitos das duas fases
observadas de ferramenta, sem nomes/saídas/caminhos. Cache web versionado.
85 regressões offline e 39 verificações de host/build/toolchain passaram neste
incremento (124 casos distintos). Nenhuma inferência, CU, novo
runtime ou admissão institucional. HISTORY novamente sem marco novo.

### Continuidade manual assistida — 2026-10-23

A visão **Resumo para continuidade**, no Contexto existente, reúne objetivo,
bloqueios e próxima ação manuais com referências da proposta/snapshot e de
candidatos selados, contagens de ferramentas do workspace e referências de
fontes já carregadas. Planos são contados como declarações do agente na conversa,
sem vínculo comprovado ao projeto; não certificam execução. Não são extraídos
comandos, saídas, conteúdo de arquivos, mensagens ou raciocínio privado.

Copiar é explícito e inclui as notas digitadas e referências do projeto; revisar
antes de compartilhar. Não envia mensagem, aprova, lê disco ou retoma tarefa.
Notas ficam em memória enquanto a visão existir; sair dela ou mudar escopo
descarta o preenchimento. Refresh no mesmo escopo preserva os campos e atualiza
as evidências. Controles antigos são inertes e consulta em andamento/incerta
não confirma aprovação; hashes e identidades malformados não sustentam recibos.

Fontes: até 100 leituras recentes/20 grupos/10 intervalos por grupo; candidatos:
até 10 referências; planos: até 20 registros/100 etapas, com metadados limitados.
As limitações aparecem no texto. Novos pedidos e autoridades continuam nos
fluxos existentes. O resumo inteiro tem limite de 32 mil caracteres com aviso
de corte; referências não confiáveis são citadas como texto literal. Esta é
preparação manual F1/F2, não durable execution,
retomada automática, compactação institucional de contexto ou scheduler.
As decisões arquiteturais anteriores permanecem pendentes. Evidências do lote
em `C:/AI/STUDIO_HANDOFF_BATCH.md`; pacote atual sempre pelo manifesto.

### Fidelidade das ferramentas de edição — 2026-10-23

Os handlers existentes de edit_file/write_file validam tipos e presença dos
argumentos antes de tocar arquivos. Substituição/conteúdo vazio continua válida
quando explícita; replace_all exige booleano real. Texto sem codificação UTF-8
válida é recusado antes de abrir para escrita. Não há ferramenta ou autoridade nova.

Uma edição lê/grava UTF-8 sem tradução automática de terminadores pelo Windows.
Preserva BOM e bytes fora da região substituída. A correspondência mantém a
equivalência de CRLF/CR/LF da leitura legada, sem tratar um CRLF como duas
quebras e sem fuzzy matching de conteúdo/indentação. O replacement é literal,
incluindo seus terminadores; isso pode produzir arquivo misto se o solicitante
misturar convenções. Não há normalização silenciosa do arquivo inteiro.

Escrita integral grava exatamente o conteúdo fornecido e conta bytes UTF-8,
não caracteres. O diff conta corretamente conteúdo iniciado por ++/--, indica
limitação e explica alterações apenas de terminadores/newline final. É uma
apresentação, não um patch selado nem evidência de promoção.

Fixtures exercitam argumentos recusados, exclusão explícita, Unicode/BOM,
CRLF/multilinha, ambiguidades, conteúdo literal e falhas sem substituição.
Testes antigos usam tmp_path/raízes de fixture, sem depender de /tmp no Windows.
TEB, dispatcher, autoridades e promoção não foram alterados. O bloqueio de
edição direta em execução elegível à promoção permanece como existente; esta
mudança não o contorna. Não se promete atomicidade multi-arquivo, recuperação
de queda de disco ou proteção contra todas as corridas de filesystem.
Evidência consolidada: `C:/AI/STUDIO_EDITING_BATCH.md`. HISTORY avaliado sem
novo marco institucional; CHANGELOG registra apenas o incremento consolidado.

### Patches de múltiplos arquivos — 2026-10-23

O handler apply_patch existente passa a validar JSON/tipos/alias único, alvos
resolvidos repetidos ou ancestrais conflitantes e UTF-8 de todas as operações
antes do loop de escrita. Erros nessa preparação não aplicam operações anteriores.
Não há transação ou rollback garantido contra falha de IO/crash/corrida posterior.

O matcher compartilhado confere linhas lógicas inteiras e únicas, com hunks
ordenados/sem sobreposição; não troca substring no meio de uma linha e exige
contexto para inserção em arquivo existente. O handler direto conserva linhas
de contexto com seus terminadores e escolhe terminador local para linhas novas;
substituição de última linha sem newline mantém esse EOF. Add File usa LF da
gramática do patch; moves/novo marcador de EOF não foram admitidos. Diff agregado
explicita corte sem perder as contagens integrais.

O adaptador Windows já reutiliza o matcher, por isso suas regressões e as de
promoção de dois arquivos são confrontadas separadamente. Não se alterou o
adaptador, seu IO, admissão, política, TEB ou recibos: não se extrapola preservação
de terminadores do handler direto para a cópia privada governada. Permanecem
exatamente dois arquivos e as restrições anteriores onde exigidos. Nenhuma
promoção N-arquivos, mecanismo de execução ou autoridade nova.
Evidências: `C:/AI/STUDIO_PATCH_BATCH.md`. HISTORY avaliado sem novo marco.

A regressão reúne 128 casos do lote principal e 41 casos distintos de
fronteira/promoção, total 169 aprovados pelo último resultado de cada caso.
Dez falhas iniciais da bateria nativa provinham do teste passar sys.executable
da venv como runtime completo. As políticas dos testes usam agora a receita
python, exercitando o seletor real existente; 19 casos nativos passaram na
repetição. O sys.executable do subprocesso interno do probe não mudou.
Logs originais com falhas foram preservados; não somar reexecuções nem tratar
esse ajuste de fixture como modificação ou relaxamento da TEB.
