# Ligand Database API (H5)

The ligand endpoints manage the PostgreSQL test set used by H5. They are
protected by the same bearer token as the rest of the data API.

## Authentication

Send `Authorization: Bearer <token>` when authentication is configured. The
health endpoint remains public. `BIMOS_API_TOKEN` is the bootstrap `admin`
token; named tokens are stored hashed and carry one of three roles:

| Role | Permissions |
|---|---|
| `viewer` | List/search ligands. |
| `editor` | Viewer permissions plus create/update ligands. |
| `admin` | Editor permissions plus soft-delete ligands and manage tokens. |

The panel stores the token in `sessionStorage` for the current browser tab; no
cookies are used.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/ligands` | Search active ligands with pagination and filters. |
| `POST` | `/api/v1/ligands` | Create a ligand. |
| `PATCH` | `/api/v1/ligands/{cid}` | Update editable fields; `cid` is immutable. |
| `DELETE` | `/api/v1/ligands/{cid}` | Soft-delete a ligand (`active=false`). |

### Search parameters

- `q`: substring in name, CID or SMILES.
- `source`: exact source filter.
- `min_mw`, `max_mw`: molar-mass bounds.
- `min_logp`, `max_logp`: LogP bounds.
- `limit`: 1-500, default 50.
- `offset`: pagination offset.

### Example

```bash
curl -H "Authorization: Bearer $BIMOS_API_TOKEN" \
  "http://127.0.0.1:8000/api/v1/ligands?q=acid&max_mw=500&limit=20"
```

```json
{
  "items": [
    {
      "id": 1,
      "name": "Caffeic acid",
      "cid": "REG_2001",
      "smiles": "OC1=CC=C(C=C1)/C=C/C(O)=O",
      "logp": 1.15,
      "molar_mass": 180.16,
      "source": "regional_phytocompound",
      "active": true
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

## Token management

Admin tokens can create, list and revoke named tokens. The plaintext token is
returned only once; only its SHA-256 hash is stored.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/tokens` | List active named tokens (no hashes). |
| `POST` | `/api/v1/tokens` | Create `{name, role}`; returns the plaintext token once. |
| `DELETE` | `/api/v1/tokens/{id}` | Revoke a named token. |

## Web panel

Open `/admin/ligands`, paste a bearer token, and use the search, create, edit,
soft-delete and token-management controls. The token is kept in
`sessionStorage` for the current browser tab; no cookies are used.
