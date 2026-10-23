# Decisões preparadas para desenvolvimento cotidiano

Status: propostas do consumidor, não aprovadas como admissão institucional.
Mandato: preparar itens 25–30 da lista offline de 2026-10-22. Não modifica
MOBS, OAP, TEB, reviewer binding, Controlled Promotion ou máquinas de estados.
Sequência de produto permanece no [roadmap](../../ROADMAP.md).

## 25. Git diff somente de leitura

Recomendação: receita tipada fechada, reutilizando o helper Git endurecido e
dispatcher/TEB existentes. Baseline e caminhos admitidos vinculados ao mandato;
comparações limitadas a variantes explícitas de working tree/index/baseline.
Sem shell, argumentos adicionais, pager, external diff, textconv, fsmonitor ou
configuração capaz de iniciar helpers. Pathspec literal; paths não concedem
leitura fora do alvo. Configuração/ambiente devem passar pelas verificações
existentes; segredos em diffs continuam exigindo limites e redação de saída.

Decisão pendente: quais comparações, tamanhos e caminhos entram no profile.
Menor ensaio posterior: fixture temporário com um arquivo admitido alterado,
um fora do escopo e configurações adversariais. Exigir diff correto, recusa
uniforme fora de escopo e nenhum helper executado. Não executado neste lote.

## 26. Git log e show

Recomendação: receitas distintas de histórico com formato/contagem fixados e
conteúdo de arquivo em revisão específica. Revisões devem resolver em commits
locais admitidos; não aceitar opções do solicitante, objetos arbitrários,
paths indiretos ou recursos externos. Histórico, mensagens e conteúdo são dados
não confiáveis, nunca autoridades. Paginação/limite explícitos; nenhuma operação
fetch, assinatura/helper ou pager implícito. Reutilizar garantias da proposta 25.

Decisão pendente: amplitude do histórico e permissão de ler conteúdo histórico
separada da leitura atual. Ensaio posterior: histórico pequeno conhecido, commit
inexistente, objeto de tipo errado, path fora de escopo e saída excessiva; provar
recusas e limites sem inferência. Nenhuma receita nova ativada aqui.

## 27. Fechamento Git governado

Commit/push/PR não decorrem de autorização para editar ou testar. Propor uma
admissão separada com arquivos exatos, digest do delta, baseline, branch e
destino remoto explícitos; revisão e validação vinculadas ao mesmo candidato.
Não incluir mudanças preexistentes ou segredos, executar hooks arbitrários,
reescrever histórico ou forçar push. Fechamento local, envio remoto e PR devem
ser efeitos distinguíveis, com recibos próprios e falhas sem falso sucesso.

Decisão pendente: autoridade que admite cada efeito e política de hooks/config,
credenciais e concorrência. Menor ensaio futuro: repositórios temporários locais
com remoto bare descartável, primeiro somente commit exato, depois push com
baseline confirmado; negar arquivos extras/drift/destino diferente. Não cria
remoto, credencial ou publicação de teste neste mandato. Os commits desta
colaboração via Codex não são prova dessa capacidade no Studio.

## 28. Promoção além de dois arquivos

Recomendação: ampliar somente após especificar unidade atômica, limites, todos
os preimages/digests, validação do conjunto, reviewer binding, concorrência e
recuperação de aplicação parcial/crash. Não dividir um delta inseparável para
contornar o limite de um ou exatamente dois arquivos. N arquivos afeta contrato
e evidência, não é só remover um contador na UI.

Decisão pendente institucional: número/volume admitidos e garantia de aplicação
e recuperação suportada na plataforma. Ensaio futuro: três arquivos com falhas
controladas em cada fronteira e drift em cada preimage, preservando o alvo e
exigindo estado final explícito. Nenhum contrato/schema/limite foi alterado.

## 29. Primeira validação Godot

Manter a [preparação existente](DEVELOPMENT_ENABLEMENT.md) e revalidar a versão,
origem do binário, baseline e arquivos antes de qualquer execução. Primeira
receita deve usar argv/executable/cwd fechados e TEB existentes, em fixture
mínimo sem autoloads, plugins, rede ou saves reais. Um caso válido e um erro
conhecido precisam discriminar os resultados; headless não constitui sandbox.
Só depois admitir um script real com dependências identificadas. Não executar
o projeto completo, alterar saves ou alegar gameplay por parse/retorno zero.

Decisão pendente: paths de scripts/cenas na raiz e receita suportada pela versão
instalada, com isolamento, efeitos e cancelamento verificados. Não iniciar
Godot/Sentinel ou implementar harness nesta preparação. Controle de gameplay
permanece uma admissão posterior de observação/input, distinta desta receita.

## 30. Rodada encerrada e objetivo comprovado

Recomendação imediata para decisão: separar conceitualmente término do
transporte/loop, efeito executado e aceitação do objetivo. Evidências necessárias
dependem do pedido: chamada válida, autorização, despacho, alvo/baseline,
receita, retorno, validação e candidato exato quando aplicável. Texto do modelo,
aprovação humana e código de saída isolados não completam essa cadeia.

Opção menor: apresentação observacional sobre estados existentes, mostrando
lacunas sem criar um novo estado institucional. Opção maior: contrato de
conclusão/recibos, sujeito a decisão arquitetural própria antes de materializar.
Não deduzir recibos ausentes nem reconstruir autoridade de registros históricos.
Ensaio futuro: simulações de promessa sem chamada, chamada inválida/negada,
falha de execução, validação divergente e cadeia completa. Somente a última
pode sustentar o objetivo específico definido; não garante qualidade universal.
Nenhuma máquina de estados foi alterada neste lote.

## Fronteiras e sequência proposta

Fonte institucional continua externa e somente leitura. Este documento é
material para decisão do fundador e autoridades responsáveis, não aprovação
por existir no Git. Priorizar 25/26 após F0 comprovado, depois fechamento e
Godot conforme necessidades reais; N arquivos e novo contrato de conclusão
exigem julgamento específico. Sem serviços/modelos/custos adicionais.
