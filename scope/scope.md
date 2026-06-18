# Mentoria Levva

# CryptoLake

---

## Objetivo do Projeto

Disponibilizar uma base analítica que permita acompanhar o desempenho dos ativos selecionados, comparar sua evolução ao longo do tempo e analisar a relação entre comportamento de mercado e sentimento dos investidores.

---

**Discovery**

→ Entendimento do cenário

**Fase 1 – Market Monitoring**

→ Monitoramento dos ativos e validação da arquitetura

**Fase 2 – Market Analytics**

→ Análises históricas, risco e correlação

**Fase 3 – Market Sentiment**

→ Contexto comportamental e sentimento de mercado

---

## 🔍 Discovery

Esta apresentação tem como objetivo realizar o alinhamento inicial do projeto, definindo as principais fontes de dados, ativos analisados, métricas de negócio e frequência de atualização.

Neste primeiro momento, o foco é compreender o domínio de criptomoedas e validar os requisitos funcionais para estruturar as definições de arquitetura futuramente. 

- Arquiterura de Dados - como solicitado pelo cliente seguiremos com uma modelagem de *star schema* com tabelas **fato** e **dimensão** dentro de uma **arquitetura medalhão (Bronze, Prata e Ouro)**
- Processo de Ingestão - definição do mecanismo de coleta, orquestração e atualização dos dados de mercado para abastecimento das camadas analíticas.
- Transformações - Preparação dos dados para que sejam consumidos em sua fase de visualização;
- Dashboard - definição de qual ferramenta será utilizada nesta fase.

### Fontes de Dados Primárias

- **Poloniex Spot API** (dados de preço e volume)
- **Binance Spot API** (dados de preço e volume)

### Moedas Selecionadas

| Ativo | Binance | Poloniex | Descrição |
| --- | --- | --- | --- |
| **Bitcoin** | BTCUSDT | BTC_USDT | Primeira e maior criptomoeda do mercado. É considerada a principal referência do setor e utilizada como indicador do comportamento geral do mercado cripto. |
| **Ethereum** | ETHUSDT | ETH_USDT | Segunda maior criptomoeda em capitalização de mercado. Possui uma plataforma de contratos inteligentes amplamente utilizada para aplicações descentralizadas (dApps). |
| **Solana** | SOLUSDT | SOL_USDT | Blockchain conhecida por sua alta velocidade de processamento e baixas taxas de transação. É uma das principais concorrentes do ecossistema Ethereum. |
| **Cardano** | ADAUSDT | ADA_USDT | Plataforma blockchain focada em escalabilidade, sustentabilidade e desenvolvimento baseado em pesquisa acadêmica e revisão por pares. |
| **Chainlink** | LINKUSDT | LINK_USDT | Criptomoeda utilizada pela rede Chainlink, que fornece oráculos para conectar contratos inteligentes a dados do mundo real, como preços, clima e eventos externos. |

### Métricas almejadas ao final do Projeto

| Métrica | Descrição Breve | Relação com OHLCV |
| --- | --- | --- |
| **Preço de Fechamento** | Valor da criptomoeda ao final do período analisado. | Utiliza diretamente o campo **Close**. |
| **Volume Negociado** | Quantidade total negociada da criptomoeda durante o período. | Utiliza diretamente o campo **Volume**. |
| **Variação 24h (%)** | Percentual de valorização ou desvalorização em relação ao período anterior. | Calculada a partir dos valores de **Close** de períodos consecutivos. |
| **Retorno Acumulado (Base 100)** | Permite comparar a evolução percentual de diferentes ativos ao longo do tempo. | Calculado utilizando a série histórica de **Close**. |
| **Volatilidade** | Mede o grau de oscilação dos preços ao longo do tempo. | Calculada a partir das variações dos valores de **Close**. |
| **Correlação BTC x Altcoins** | Mede o quanto os movimentos de preço das moedas são semelhantes ao Bitcoin. | Calculada utilizando as séries históricas de **Close** dos ativos. |
| **Fear & Greed Index** | Indicador que mede o sentimento do mercado entre medo e ganância. | Não utiliza OHLCV. Obtido de uma fonte externa de sentimento. |

> O conjunto OHLCV (Open, High, Low, Close e Volume) será a principal fonte de dados do projeto. A partir dele serão calculadas métricas como variação de preço, retorno acumulado, volatilidade e correlação. Já as métricas de Dominância do Bitcoin e Fear & Greed Index dependem de fontes complementares de mercado e sentimento.
> 

### Frequência de Atualização

| Fonte | Frequência |
| --- | --- |
| Dados de Mercado (Spot) | Horária, Diária |
| Fear & Greed Index | Diária |

---

## 🚀 Fase 1 — Foundation & Market Data

### Objetivo

Construir a fundação técnica do CryptoLake, validando a arquitetura de dados ponta a ponta e disponibilizando os primeiros indicadores de mercado para análise dos ativos selecionados.

Nesta fase serão implementadas as camadas Bronze, Silver e Gold, além da modelagem inicial do produto de dados. O foco será a ingestão dos dados de mercado (OHLCV) e a disponibilização das métricas básicas necessárias para acompanhamento dos ativos.

### Escopo Técnico

- Definição da arquitetura Medallion (Bronze, Silver e Gold)
- Modelagem conceitual e lógica do produto
- Construção das tabelas dimensionais e fatos iniciais
- Implementação da ingestão via Poloniex Spot API e Binance Spot API
- Estruturação do dicionário de dados
- Tratamento e padronização dos dados OHLCV

### Métricas

| Métrica | Objetivo |
| --- | --- |
| Preço de Fechamento | Acompanhar a evolução do valor dos ativos ao longo do tempo. |
| Volume Negociado | Avaliar o nível de atividade e interesse do mercado em cada ativo. |
| Variação 24h (%) | Identificar movimentos de valorização e desvalorização dos ativos. |

### Entregáveis

- Arquitetura documentada
- Modelo conceitual
- Modelo lógico
- Dicionário de dados
- Pipeline de ingestão
- Camadas Bronze, Silver e Gold
- Dashboard MVP com métricas básicas

### Prazo Estimado

📆 ~3 **semanas | 08/07/2026**

---

## 📈 Fase 2 — Advanced Market Analytics

### Objetivo

Expandir as capacidades analíticas do CryptoLake através da implementação de métricas derivadas e análises comparativas entre Bitcoin e Altcoins.

Nesta fase o foco deixa de ser apenas a disponibilização dos dados e passa a ser a geração de conhecimento analítico a partir da evolução histórica dos ativos.

### Escopo Técnico

- Evolução da camada Gold
- Implementação de métricas derivadas
- Comparação entre ativos
- Consolidação dos indicadores históricos

### Métricas

| Métrica | Objetivo |
| --- | --- |
| Retorno Acumulado (Base 100) | Comparar a performance dos ativos ao longo do tempo. |
| Volatilidade | Avaliar o nível de risco e oscilação dos ativos. |
| Correlação BTC x Altcoins | Entender o relacionamento entre os movimentos do Bitcoin e das demais moedas. |

### Entregáveis

- Dashboard comparativo
- Indicadores de risco
- Matriz de correlação
- Documentação das fórmulas de negócio
- Camada Gold evoluída

### Prazo Estimado

📆 **2 semanas | 22/07/2026**

---

## 🧠 Fase 3 — Market Sentiment Analytics

#### Objetivo

Complementar as análises de mercado através da incorporação de indicadores de sentimento dos investidores.

O objetivo desta fase é avaliar a relação entre o comportamento dos preços e o sentimento predominante do mercado, adicionando uma camada adicional de contexto às análises realizadas nas fases anteriores.

#### Fontes de Dados

- Alternative.me Fear & Greed Index

#### Escopo Técnico

- Integração da API Fear & Greed
- Modelagem dos dados de sentimento
- Integração com os dados de mercado
- Construção de análises temporais entre sentimento e preço

#### Métricas

| Métrica | Objetivo |
| --- | --- |
| Fear & Greed Index | Monitorar o sentimento predominante dos investidores. |

#### Entregáveis

- Pipeline de ingestão de sentimento
- Dashboard de sentimento
- Indicadores de mercado e sentimento integrados
- Relatório analítico de comportamento do mercado

## Prazo Estimado

📆 **2 semanas | 05/08/2026**

---

## 📅 Cronograma Macro

| Fase | Objetivo Principal | Data Início | Data Entrega | Duração |
| --- | --- | --- | --- | --- |
| Discovery | Alinhamento, fontes, ativos e métricas | 03/06/2026 | 17/06/2026 | 2 semanas |
| Fase 1 | Foundation & Market Data | 18/06/2026 | 08/07/2026 | 3 semanas |
| Fase 2 | Advanced Market Analytics | 09/07/2026 | 22/07/2026 | 2 semanas |
| Fase 3 | Market Sentiment Analytics | 23/07/2026 | 05/08/2026 | 2 semanas |