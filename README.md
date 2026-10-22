<p align="center"><img src="static/brand/studio-wordmark.svg" alt="MOBS Studio" width="360"></p>

MOBS Studio é o ambiente consumidor de engenharia agêntica governado pelo MOBS. Reúne conversas, projetos, modelos, ferramentas e evidências em uma experiência de trabalho em camadas.

**MOBS governa; Studio consome e executa.** A interface não concede permissões, não aprova mandatos e não retoma execuções por conta própria.

O rebrand deste working tree está em revisão local. MS é uma assinatura candidata, não uma identidade institucional definitivamente aprovada.

[Configuração](docs/setup.md) · [Capability Map](docs/product/PLATFORM_CAPABILITY_MAP.md) · [Roadmap](ROADMAP.md) · [Contribuições](CONTRIBUTING.md)

## Quick Start

Repositório consumidor oficial: [`gitmanoz/odysseus-mobs`](https://github.com/gitmanoz/odysseus-mobs), branch principal atual `dev`.

```bash
git clone --branch dev https://github.com/gitmanoz/odysseus-mobs.git
cd odysseus-mobs
cp .env.example .env
docker compose up -d --build
```

Abra `http://localhost:7000` quando os containers estiverem saudáveis. A senha inicial do administrador aparece em `docker compose logs odysseus`. Nomes técnicos legados são preservados para compatibilidade.

## Desktop Windows

Build: `build-windows-portable.ps1` com `Odysseus.spec`. Distribuição pública: `dist/MOBS Studio/MOBS Studio.exe`. Mantenha `_internal` ao lado do executável.

Dados e identidade de instalação continuam em `%LOCALAPPDATA%\Odysseus`. O rebrand não migra nem apaga bancos, autenticação, configurações, políticas ou reviewer bindings.

O provedor local precisa estar em execução. Ter um modelo instalado no Ollama não significa que seu servidor esteja atendendo. Conecte o endpoint pela configuração de modelos existente.

## Capacidades e estado

- Chat e Agent Loop: modelos locais/API, sessões, streaming, arquivos e ferramentas existentes.
- Workspace e execução governada: baseline, mandato, validação privada e promoção controlada.
- Perfis versionados: receitas Python e leitura tipada de identidade/status Git no escopo implementado.
- Memory, Skills, MCP e integrações herdadas: superfícies contextuais e avançadas.
- Consulta de pendências por sessão: não recupera execução durável após restart.

O [Capability Map](docs/product/PLATFORM_CAPABILITY_MAP.md) distingue capacidades disponíveis, parciais e futuras; o [Roadmap](ROADMAP.md) define a ordem de materialização. Visão futura não é funcionalidade já implementada.

## Segurança, origem e licença

Mantenha autenticação habilitada nas instalações reais e não exponha portas de modelos diretamente à internet. Dados privados, credenciais e estado operacional local não entram no Git. [Notas de segurança](docs/setup.md#security-notes).

Derivado do projeto [Odysseus](https://github.com/odysseus-dev/odysseus). Créditos, autoria e atribuições permanecem em [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) e [LICENSE](LICENSE).

**AGPL-3.0-or-later.** O rebrand público não modifica a licença nem a autoria da base original.
