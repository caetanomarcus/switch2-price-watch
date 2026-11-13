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

## Rodando no seu computador pra destravar Mercado Livre e Magalu

O GitHub Actions roda na nuvem, de um IP de datacenter. Mercado Livre e
Magalu detectam que a conexão não é de um navegador real (ex: a Mercado
Livre devolve um header `x-is-search-bot: true` pra requisições simples)
e bloqueiam, mesmo vindo de IP residencial. Um **navegador real
(Chromium via Playwright)** rodando do **seu próprio computador** tem
chance real de passar por esse bloqueio.

### Primeira vez (configuração)

Dê duplo clique em `atualizar_precos.command` (ou rode `bash
atualizar_precos.command` no Terminal). Na primeira vez ele vai:
1. Instalar as dependências Python
2. Baixar o Chromium do Playwright (pode levar alguns minutos)
3. Rodar o scraper
4. Enviar o resultado pro GitHub automaticamente

### Próximas vezes

É só dar duplo clique de novo quando quiser atualizar os preços
manualmente. Leva uns 30-60 segundos.

### Se o `git push` pedir login

Seu Mac precisa estar autenticado no GitHub (normal se você já usa git
por aí). Se pedir usuário/senha e a senha não funcionar, o GitHub exige
um *token* de acesso pessoal em vez de senha normal - crie um em
https://github.com/settings/tokens e use ele no lugar da senha, ou
configure o GitHub CLI (`gh auth login`) antes de rodar o script.
