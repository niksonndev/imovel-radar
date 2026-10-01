# Imóvel Radar · 15 s launch film (demo)

Carpeta de trabajo: `docs/demo-film/work/`. Comp con onetake (una única cámara continua; cada frontera lleva un elemento en pantalla). Textos en pt-BR.

## Beat sheet (t · beat · qué lleva la frontera)

| t (s) | beat | qué se ve | carry a la siguiente |
|---|---|---|---|
| 0–2.6 | La barra digita la frase libre | barra con ">" y cursor, digita "Apartamento de 2 quartos na Ponta Verde, até R$ 2.500" | la barra persiste (ancla) |
| 2.6–3.1 | Enviar → chips | clic en enviar; chips Aluguel / Apartamentos / Ponta Verde / até R$ 2.500 / 2+ quartos | barra → chips |
| 3.6–4.6 | Sweep de radar | el barrido radial sale de la confirmación y abre el chat | sweep → card |
| 4.15–6.2 | Match (cartel) | cartel: foto, "Apartamento em Ponta Verde", R$ 2.100/mês, 2 quarto(s), 65 m², Ver anúncio | el cartel se encoge (morphRect, misma identidad #scard) |
| 6.6–7.5 | "Acompanha este" → fila | el cartel morfea a la fila "Acompanhando · ✅ No ar · preço base R$ 2.100" | la fila sostiene la quietud |
| 7.6–9.5 | ESTATALIDAD | solo pulso ámbar tenue sobre la fila; cámara quieta | los dígitos del precio son el elemento que sigue |
| 9.6–10.5 | Precio rueda R$ 2.100 → R$ 1.800 (verde) | burbuja "📉 Preço caiu R$ 300"; usuario digita "e o preço por m² na região?" | respuesta se pliega a la barra |
| 11.7–12.3 | Respuesta de mercado | "Média em Ponta Verde · aluguel · R$ 45/m² · 86 anúncios" con <small>dados de exemplo</small> | la respuesta se pliega a la barra |
| 12.6–13.1 | Herramientas del asistente | chips: listar alertas · remover alerta · parar de seguir | barra → lockup |
| 13.4–15 | Cierre | "Imóvel Radar" (ícono radar) + CTA "Começar grátis no Telegram", reposo final | — |

## Look
Fondo casi negro `#050505` con retícula de puntos tenue; acentos azul `#0A84FF` (interfaz), verde `#009866` (buenas noticias, caída de precio), ámbar `#FF9F0A` (vigilando). Tipografías del producto: Poppins (títulos), Inter (UI), JetBrains Mono (barra de prompt y números). Foto del imóvil generada con PIL (licenciable). Sin cortes: una pieza continua.

## Números (draft 1080p30)
- `verify_promo.py` → VERDICT: PASS. Cadence CV 0.41 (≥.25); rest 0.478 muerto / 3.17 s quietud; burst presente; audio peak −8 dBFS, sin recortes; continuidad carry 1.00 (0 fronteras, mundo continuo — se juzga a ojo); curvas peak 1912 px/frame con shutter 180°.
- 450 frames, 900 capturas, 33 s de render en 6 workers, 0 errores de página.

## Archivos
- `comp.html` + `motion.js` + `fonts/` (Poppins 500/600, Inter, JB extraídas del build del frontend) + `photo.jpg` (foto generada) + `sfx.py` → `sfx.wav`.
- `draft.mp4` (1080p30). Final 4K60 pendiente hasta aceptar el corte.

## Datos / reglas
- Precios de la fixture real del producto: R$ 2.100 → R$ 1.800, 2 quartos, Ponta Verde (test de alert_intelligence). Número de mercado etiquetado "dados de exemplo".
- Sin match "%, de probabilidad; sin usuario/chat ID/telefono/URL reales; "Ver anúncio" no tiene enlace (botón ficticio).
- Nota de contenido (revisar con el fundador): el inventario marca que el producto aún no tiene herramienta de IA para "acompañar/parar de seguir" ni notificación instantánea; el film lo muestra según el brief. El beat de mercado usa media de muestra, no dato de producción.