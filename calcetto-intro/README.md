# Intro Calcetto – Rossi vs Blu

Motion graphic di ~15 secondi (1920×1080, 60 fps, audio incluso) che presenta le due squadre.

**Video finito:** [`calcetto-intro.mp4`](calcetto-intro.mp4)

## Struttura

| Tempo | Scena |
|-------|-------|
| 0 – 3 s | La palla arriva in camera → titolo **CALCETTO** → «Rossi vs Blu» |
| 3 – 7 s | **Squadra Rossa**: Massi, Matte, Fede M., Lippa, Thomas |
| 7 – 11 s | **Squadra Blu**: Salmi, Dani, Cristian, Bik, Luciano |
| 12 – 14,8 s | Scontro **VS** con riepilogo delle due formazioni → flash bianco finale |

L'audio (musica a 120 BPM + effetti) è sintetizzato da `audio.py` ed è sincronizzato ai tempi dell'animazione.
Il flash bianco finale serve da stacco verso il tuo video.

## Modificare e rigenerare

- **Nomi / titolo / tempi:** in cima allo `<script>` di `index.html` (`TEAMS`, `TITLE`, `T`).
- **Anteprima:** apri `index.html` nel browser (clic o barra spaziatrice per ripartire).
- **Rigenera il video:** `./make.sh` (richiede Node, Python con `numpy`+`scipy`, ffmpeg e Chromium).
  Per 30 fps: `FPS=30 ./make.sh`.

Font: Anton e Barlow Condensed (SIL OFL, vedi `fonts/`). Animazioni: [GSAP](https://gsap.com).
