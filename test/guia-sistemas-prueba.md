# Guía de Sistemas de Prueba — BIMOS

## Estructura del Directorio `test/`

```
test/
├── APO/          → 1AKI.pdb            (Estructura apo: proteína sin ligando)
├── DOCKING/      → JZ4.pdb, 3HTB.pdb   (Receptores para acoplamiento molecular)
└── HOLO/         → JZ4.pdb, 3HTB.pdb   (Estructuras holo: proteína con ligando unido)
```

### Mapeo contra los Pipelines

| Carpeta | Pipeline | Comando | Uso |
|---|---|---|---|
| `APO/1AKI.pdb` | MD (Apo) | `bimos workflow -p test/APO/1AKI.pdb` | Simulación de proteína sin ligando. 1AKI = lisozima (1016 átomos, 79 HETATM cristalográficos) |
| `DOCKING/JZ4.pdb` | Docking | `bimos dock test/DOCKING/JZ4.pdb <ligands>` | Receptor pequeño (1.2 KB) para pruebas rápidas de docking. JZ4 = 2-propilfenol |
| `DOCKING/3HTB.pdb` | Docking | `bimos dock test/DOCKING/3HTB.pdb <ligands>` | Receptor grande (103 KB, modelo Modeller) para pruebas de docking a escala real |
| `HOLO/JZ4.pdb` | MD (Holo) | `bimos workflow -p test/HOLO/JZ4.pdb --ligand-gro ... --ligand-itp ...` | Complejo proteína-ligando pequeño |
| `HOLO/3HTB.pdb` | MD (Holo) | `bimos workflow -p test/HOLO/3HTB.pdb --ligand-gro ... --ligand-itp ...` | Complejo proteína-ligando grande |

> **Nota:** Los archivos en `DOCKING/` y `HOLO/` son idénticos (mismos PDB). La separación es conceptual: `DOCKING/` para el pipeline de acoplamiento, `HOLO/` para el pipeline de dinámica molecular en modo holo.

---

## Matriz de Opciones por Pipeline

### 1. Docking: `bimos dock`

```
bimos dock [OPCIONES] PROTEIN_PDB LIGANDS_INPUT
```

| Opción | Flag | Valor | Descripción |
|---|---|---|---|
| **Origen de ligandos** | *(por defecto)* | Ruta a archivo `.sdf` | Archivo SDF multi-molécula propio del usuario |
| | `-d, --dataset` | Nombre del dataset | Lectura desde base de datos SQLite curada (`candidates` o `phytocompounds`) |
| **Output** | `-o, --output` | Directorio | Directorio de salida (default: workspace/docking/) |
| **Ejecución** | `-b, --background` | — | Ejecutar en segundo plano |
| | `-g, --gui` | — | Abrir dashboard GUI para monitoreo |
| **Rendimiento** | `--max` (global) | — | Usar todos los CPUs, mayor exhaustividad |
| **Grid** | *(en YAML)* | `auto` / `manual` | `auto`: calcula la caja desde el receptor; `manual`: requiere center/size |

**Ejemplos:**

```bash
# Modo SDF propio
bimos dock test/DOCKING/3HTB.pdb mis_ligandos.sdf -o resultados/

# Modo base de datos curada
bimos dock test/DOCKING/JZ4.pdb phytocompounds -d -o resultados/

# Modo máximo rendimiento
bimos dock --max test/DOCKING/3HTB.pdb ligandos.sdf
```

---

### 2. Predicción de Estructuras: `bimos predict` / `bimos predict-boltz`

```
bimos predict [OPCIONES] FASTA_FILE
bimos predict-boltz [OPCIONES] FASTA_FILE
```

| Opción | Pipeline | Flag | Descripción |
|---|---|---|---|
| **Modelo** | ESMFold | `bimos predict` | ~8 GB, CPU, OpenFold optimizado. Rápido. Recycles default: 3 |
| | Boltz-1 | `bimos predict-boltz` | Modelo generativo, múltiples modelos. Default: 5 corridas |
| **Recycles** | ESMFold | `--recycles` | Número de reciclados (default: 3) |
| **Modelos** | Boltz-1 | `-n, --models` | Número de modelos Boltz a ejecutar (default: 5) |
| **Output** | Ambos | `-o, --output` | Directorio de salida |
| **Ejecución** | Ambos | `-b, --background` | Ejecutar en segundo plano |
| | Ambos | `-g, --gui` | Abrir dashboard GUI |

**Ejemplos:**

```bash
# Predicción con ESMFold (rápido)
bimos predict test/APO/1AKI.fasta -o estructuras/

# Predicción con Boltz-1 (mayor precisión, más lento)
bimos predict-boltz test/APO/1AKI.fasta -n 10 -o estructuras/
```

---

### 3. Dinámica Molecular: `bimos workflow`

```
bimos workflow [OPCIONES]
```

| Opción | Modo | Flag | Descripción |
|---|---|---|---|
| **Modo APO** | Proteína sola | `-p test/APO/1AKI.pdb` | Proteína sin ligando. SDM default: 250M pasos (500 ns) |
| **Modo HOLO** | Complejo | `-p test/HOLO/JZ4.pdb --ligand-gro LIG.gro --ligand-itp LIG.itp` | Proteína + ligando. SDM default: 50M pasos (100 ns) |
| **Output** | Ambos | `-o, --output` | Directorio de salida |
| **Ejecución** | Ambos | `-b, --background` | Ejecutar en segundo plano |
| | Ambos | `-g, --gui` | Abrir dashboard GUI |

**Ejemplos:**

```bash
# Simulación APO (proteína sin ligando)
bimos workflow -p test/APO/1AKI.pdb -o md_apo/

# Simulación HOLO (complejo proteína-ligando)
bimos workflow -p test/HOLO/JZ4.pdb --ligand-gro jz4.gro --ligand-itp jz4.itp -o md_holo/
```

---

### 4. Química Cuántica: `bimos qm-orca` / `bimos qm-g16`

```
bimos qm-orca [OPCIONES] DIRECTORIO
bimos qm-g16 [OPCIONES] DIRECTORIO
```

| Opción | Flag | Descripción |
|---|---|---|
| **Jobs paralelos** | `-j, --jobs` | Máximo de trabajos paralelos (default: 2) |
| **Carga total** | `-q, --charge` | Carga total del sistema (default: 0) |
| **Ejecución** | `-b, --background` | Ejecutar en segundo plano |
| | `-g, --gui` | Abrir dashboard GUI |

---

## Resumen Visual de Opciones

```
┌─────────────────────────────────────────────────────────────┐
│                    BIMOS — SISTEMAS DE PRUEBA                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  PREDICCIÓN DE ESTRUCTURAS                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  FASTA ──┬── ESMFold  (─recycles N)                 │   │
│  │          └── Boltz-1  (─models N)                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  DOCKING                                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  PDB + ─┬── SDF propio  (ruta a .sdf)               │   │
│  │         └── DB curada   (─dataset <nombre>)          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  DINÁMICA MOLECULAR                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  PDB ──┬── APO  (solo proteína)                     │   │
│  │        └── HOLO (proteína + ─ligand-gro ─ligand-itp)│   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  QUÍMICA CUÁNTICA                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  .gro ──┬── ORCA  (─j N ─q N)                       │   │
│  │         └── G16   (─j N ─q N)                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  FLAGS TRANSVERSALES:                                       │
│  ─b (background)  ─g (GUI)  ─o (output)  ──max (máximo)   │
└─────────────────────────────────────────────────────────────┘
```

## Convención de Nomenclatura para Nuevos Sistemas de Prueba

```
test/
├── APO/{UNPCODE}.pdb           → Proteína sin ligando (MD workflow)
├── DOCKING/{UNPCODE}.pdb       → Receptor para docking
└── HOLO/{UNPCODE}.pdb          → Complejo con ligando (MD workflow)
    HOLO/{UNPCODE}_lig.gro      → Ligando en formato GROMACS GRO
    HOLO/{UNPCODE}_lig.itp      → Parámetros del ligando en formato ITP
```
