# Render Blender (opzionale)

La dashboard mostra già un monitor **3D interattivo in tempo reale** (Three.js): si ruota col mouse,
ha riflessi e illuminazione, e all'apertura di un monitor parte una rotazione completa. Non serve Blender
per usarlo.

Questo script serve a produrre, **a parte**, un render **fotorealistico** dello stesso monitor con Cycles:
un fermo immagine e una rotazione completa come sequenza PNG con sfondo trasparente. È utile per immagini
di presentazione, per il README, o come intro pre-renderizzata da mostrare alla selezione del monitor.

> Nota: Blender non era disponibile nell'ambiente in cui questo script è stato scritto, quindi non è
> stato eseguito qui. È Python standard per l'API di Blender 4.x; segnala eventuali problemi.

## Requisiti

- Blender 4.x
- Per tempi ragionevoli, una GPU (il fallback su CPU funziona ma è lento)

## Uso

Dalla cartella del progetto:

```sh
blender --background --python blender/render_monitor.py -- --frames 72 --samples 256 --out blender/out
```

Opzioni dopo `--`:

| Opzione | Significato | Default |
|---|---|---|
| `--frames N` | fotogrammi del giro completo | 72 |
| `--samples N` | campioni Cycles per fotogramma | 192 |
| `--res W H` | risoluzione | 1280 720 |
| `--still-only` | solo il fermo immagine | — |
| `--out DIR` | cartella di output | `blender/out` |
| `--device CPU\|GPU` | dispositivo di render | GPU se disponibile |

Risultato:

- `blender/out/still.png` — fermo immagine
- `blender/out/turntable/frame_000.png … frame_NNN.png` — la rotazione

Le strisce LED sono renderizzate di un bianco neutro di proposito: i colori reali li applica la dashboard.

## Usare la rotazione pre-renderizzata nella dashboard

Un modo semplice è trasformare la sequenza in una `.webp` animata o in un video e mostrarla come intro
alla selezione del monitor, lasciando poi il 3D interattivo di Three.js. La dashboard non la carica da
sola: apri una richiesta se vuoi che venga integrata, indicando dove metti i file generati.
