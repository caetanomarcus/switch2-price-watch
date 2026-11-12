# Switch 2 Price Watch

Site que monitora automaticamente preços de jogos de **Nintendo Switch 2**
em lojas brasileiras (Mercado Livre, Kabum, Magalu e Amazon BR), detecta
promoções e mostra o histórico de menor preço.

🔗 Site publicado via GitHub Pages: (ativar em Settings → Pages → branch `main` → pasta `/`)

## Como funciona

1. `scraper.py` varre as páginas de busca/categoria de jogos de Switch 2
   em cada loja, pega título, preço atual e preço "de tabela", e calcula
   o desconto.
2. O histórico de cada jogo é salvo em `data/prices.json` (um arquivo só,
   versionado no próprio repositório — sem banco de dados).
3. Um workflow do **GitHub Actions** (`.github/workflows/update-prices.yml`)
   roda o scraper todo dia às 09h (horário de Brasília) e comita o
   `prices.json` atualizado automaticamente.
4. `index.html` é uma página estática que lê esse JSON e mostra os
   jogos, ordenados por maior desconto por padrão.

## Rodar localmente

```bash
pip install -r requirements.txt
python scraper.py
# depois abra index.html num servidor local, ex:
python -m http.server 8000
```

## Avisos importantes

- **Isso é scraping de HTML público, não uso de API oficial.** As lojas
  podem mudar o layout da página a qualquer momento — quando isso
  acontece, a loja afetada simplesmente para de aparecer nos resultados
  até alguém atualizar os seletores em `scraper.py`. As outras lojas
  continuam funcionando normalmente (os erros são isolados por loja).
- **Amazon BR é a mais instável**, pois bloqueia scraping agressivamente
  (CAPTCHA/anti-bot) e seus Termos de Uso proíbem coleta automatizada.
  A função correspondente falha de forma silenciosa (lista vazia) quando
  bloqueada, em vez de insistir. O caminho mais robusto e dentro das
  regras seria usar a Amazon PA-API via Programa de Associados.
- Rode o scraper manualmente a qualquer momento via aba **Actions** do
  GitHub → "Atualizar preços Switch 2" → "Run workflow".

## Ativando o site (GitHub Pages)

No repositório: **Settings → Pages → Source: Deploy from a branch →
Branch: `main` / pasta `/ (root)`**. Depois de alguns minutos o site
fica disponível em `https://<seu-usuario>.github.io/<repo>/`.
