# Switch 2 Price Watch

Site que monitora automaticamente preços de jogos de **Nintendo Switch 2**
na Kabum, Amazon BR e no agregador de ofertas **Promobit**, detecta
promoções e mostra o histórico de menor preço.

🔗 Site publicado via GitHub Pages: (ativar em Settings → Pages → branch `main` → pasta `/`)

## Como funciona

1. `scraper.py` varre as páginas de busca/categoria de jogos de Switch 2
   em cada fonte, pega título, preço atual e preço "de tabela", e calcula
   o desconto.
2. O histórico de cada jogo é salvo em `data/prices.json` (um arquivo só,
   versionado no próprio repositório — sem banco de dados).
3. Um workflow do **GitHub Actions** (`.github/workflows/update-prices.yml`)
   roda o scraper todo dia às 09h (horário de Brasília) e comita o
   `prices.json` atualizado automaticamente — 100% na nuvem, sem precisar
   de nenhum computador ligado.
4. `index.html` é uma página estática que lê esse JSON e mostra os
   jogos, ordenados por maior desconto por padrão.

## Rodar localmente

```bash
pip install -r requirements.txt
python scraper.py
# depois abra index.html num servidor local, ex:
python -m http.server 8000
```

## Fontes e limitações

- **Kabum**: funciona de forma estável, lendo os dados embutidos na
  própria página (`__NEXT_DATA__`).
- **Amazon BR**: bloqueia scraping agressivamente (CAPTCHA/anti-bot) e
  seus Termos de Uso proíbem coleta automatizada. A função falha de
  forma silenciosa (lista vazia) quando bloqueada, em vez de insistir.
  O caminho mais robusto e dentro das regras seria a Amazon PA-API via
  Programa de Associados.
- **Promobit** é um agregador (não vende direto) — lista ofertas postadas
  pela comunidade, com a loja de origem entre parênteses, ex: "Promobit
  (Amazon)". O scraper pagina pelos destaques recentes da categoria
  "Nintendo Switch" usando o cursor interno do site (até
  `PROMOBIT_MAX_PAGES` páginas, hoje 8).
- **Mercado Livre e Magazine Luiza foram removidos** do scraper: ambos
  detectam automação mesmo com navegador real (Playwright) e IP
  residencial — não é bloqueio de IP, é fingerprint de bot. **Pelando**
  foi avaliado e descartado pelo mesmo motivo (desafio Cloudflare bloqueia
  até requisição simples).
- **Isso é scraping de HTML público, não uso de API oficial.** Qualquer
  fonte pode mudar o layout da página a qualquer momento — quando isso
  acontece, ela simplesmente para de aparecer nos resultados até alguém
  atualizar o parser em `scraper.py`. Os erros são isolados por fonte.
- Rode o scraper manualmente a qualquer momento via aba **Actions** do
  GitHub → "Atualizar preços Switch 2" → "Run workflow".

## Ativando o site (GitHub Pages)

No repositório: **Settings → Pages → Source: Deploy from a branch →
Branch: `main` / pasta `/ (root)`**. Depois de alguns minutos o site
fica disponível em `https://<seu-usuario>.github.io/<repo>/`.
