# Mon Marché Meal Planner — Backend

Backend Python FastAPI pour le projet **Mon Marché Meal Planner**.

Il permet à une application iOS de :

- parcourir les recettes stockées dans Notion ;
- générer une liste de courses consolidée à partir du contenu des pages recette ;
- associer les ingrédients à des produits [mon-marché.fr](https://www.mon-marche.fr) ;
- préparer un panier via Playwright ;
- laisser l'utilisateur finaliser la commande **manuellement** sur l'interface officielle mon-marché.fr.

Le backend **n'automatise jamais le paiement** et ne stocke **aucune information bancaire**.

## Architecture

```
iOS App  --->  FastAPI Backend  --->  Notion API (recettes)
                      |
                      +--> SQLite (mappings, commandes)
                      |
                      +--> Playwright (préparation panier mon-marché.fr)
```

Couches principales :

- **API** : routes REST protégées par Bearer token
- **Services** : Notion, parsing recette, consolidation, normalisation, mappings, commandes, bot Playwright
- **DB** : SQLAlchemy + SQLite (MVP)
- **Scripts** : sauvegarde manuelle de session navigateur mon-marché.fr

## Base Notion utilisée

Le MVP utilise une seule base existante :

- Nom : **🍛 Livre de recettes**
- URL : https://www.notion.so/17f6d0cbfb9d80fe9281f92f84cb1a76

Propriétés mappées :

| Propriété Notion      | Champ API |
|-----------------------|-----------|
| Nom                   | name      |
| État                  | status    |
| Note                  | rating    |
| Sélection multiple    | tags      |

Les ingrédients sont extraits depuis le **contenu textuel** de chaque page recette. Il n'existe pas de base Ingredients séparée.

Les noms de propriétés Notion sont centralisés dans `app/core/config.py` (`NotionPropertyNames`).

## Prérequis

- [uv](https://docs.astral.sh/uv/) (gestionnaire de paquets et d'environnement Python)

Installation de uv :

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Installation locale

```bash
uv sync
uv run playwright install chromium
# Linux uniquement :
uv run playwright install-deps chromium
```

Copier la configuration :

```bash
cp .env.example .env
```

Renseigner au minimum :

- `NOTION_TOKEN`
- `NOTION_RECIPES_DATABASE_ID=17f6d0cbfb9d80fe9281f92f84cb1a76`
- `API_AUTH_TOKEN`

## Installation sur VPS Debian

```bash
sudo apt update
sudo apt install -y curl

curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"

git clone <votre-repo> monmarche-backend
cd monmarche-backend

uv sync
uv run playwright install chromium
uv run playwright install-deps chromium

cp .env.example .env
nano .env
mkdir -p data/debug
```

Lancement avec uvicorn :

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

En développement :

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Variables d'environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `NOTION_TOKEN` | Token d'intégration Notion | — |
| `NOTION_RECIPES_DATABASE_ID` | ID de la base recettes | — |
| `DATABASE_URL` | URL SQLAlchemy | `sqlite:///./monmarche.db` |
| `MONMARCHE_STORAGE_STATE_PATH` | Fichier session Playwright | `./data/monmarche_storage_state.json` |
| `MONMARCHE_BASE_URL` | URL du site | `https://www.mon-marche.fr` |
| `MONMARCHE_CART_URL` | URL du panier | `https://www.mon-marche.fr/panier` |
| `APP_ENV` | Environnement | `dev` |
| `API_AUTH_TOKEN` | Token Bearer API | — |

## Authentification API

Tous les endpoints sauf `GET /health` exigent :

```http
Authorization: Bearer <API_AUTH_TOKEN>
```

## Endpoints principaux

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/health` | Santé de l'API |
| GET | `/recipes` | Liste des recettes Notion |
| GET/POST/PATCH/DELETE | `/mappings` | CRUD mappings produits |
| POST | `/orders/preview` | Prévisualisation de commande |
| GET | `/orders/{order_id}` | Détail commande |
| GET | `/orders/{order_id}/status` | Statut commande |
| POST | `/orders/{order_id}/prepare-cart` | Préparation panier Playwright |
| GET | `/monmarche/session-status` | État de la session navigateur |

## Exemples curl

Health (public) :

```bash
curl http://localhost:8000/health
```

Endpoint protégé :

```bash
curl -H "Authorization: Bearer dev-token" http://localhost:8000/recipes
```

Créer un mapping :

```bash
curl -X POST http://localhost:8000/mappings \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -d '{
    "normalized_ingredient_name": "tomate",
    "monmarche_product_name": "Tomates rondes",
    "monmarche_product_url": "https://www.mon-marche.fr/...",
    "search_query": "tomate",
    "package_quantity": 1,
    "package_unit": "piece",
    "confidence_score": 1.0
  }'
```

Créer une preview :

```bash
curl -X POST http://localhost:8000/orders/preview \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -d '{
    "recipe_ids": ["notion-page-id"],
    "people_count": 2,
    "desired_delivery_date": "2026-06-01"
  }'
```

Préparer le panier :

```bash
curl -X POST http://localhost:8000/orders/<order_id>/prepare-cart \
  -H "Authorization: Bearer dev-token"
```

## Sauvegarder la session mon-marché.fr

Le backend ne demande jamais votre mot de passe en terminal.

```bash
uv run python scripts/save_monmarche_session.py
```

1. Une fenêtre Chromium s'ouvre sur mon-marché.fr
2. Connectez-vous **manuellement**
3. Revenez au terminal et appuyez sur Entrée
4. La session est enregistrée dans `MONMARCHE_STORAGE_STATE_PATH`

## Tests

```bash
uv run pytest
```

Les tests couvrent les services purs (normalisation, parser, consolidation, mappings) et l'endpoint `/health`, sans Notion ni Playwright.

## Flux utilisateur iOS

1. L'app liste les recettes via `GET /recipes`
2. L'utilisateur sélectionne des recettes, un nombre de personnes et une date
3. L'app appelle `POST /orders/preview`
4. L'app affiche produits mappés, mappings manquants et ingrédients incertains
5. L'utilisateur complète les mappings si nécessaire
6. L'app appelle `POST /orders/{id}/prepare-cart`
7. L'app ouvre `cart_url` dans une WebView ou Safari
8. L'utilisateur vérifie, choisit son créneau et paie **lui-même** sur mon-marché.fr

## Limites connues du MVP

- Parser d'ingrédients simple, adaptable selon le format réel des pages Notion
- Pas de conversion d'unités avancée
- Sélecteurs Playwright placeholder à affiner avec le vrai DOM mon-marché.fr
- Préparation de panier synchrone
- SQLite local (pas de PostgreSQL / Redis / Celery)
- Pas de statut « commande payée » automatique

## Sécurité

- Aucun paiement automatisé
- Aucun stockage de mot de passe mon-marché.fr
- Aucun stockage d'informations bancaires
- Aucune tentative de contournement captcha / 3DS / anti-bot
- Secrets uniquement via variables d'environnement

## Structure du dépôt

```
app/
  main.py
  core/
  api/routes/
  schemas/
  services/
  db/
scripts/
tests/
pyproject.toml
uv.lock
.env.example
```
