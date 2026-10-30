Island heading fonts are vendored from Google Fonts and licensed under the
SIL Open Font License; the license for each family is included here.

- Orbitron: variable 400–900, Latin WOFF2.
- Chakra Petch: normal 500/700, Latin WOFF2; italic 700, full TTF.
- Rye: normal 400, Latin WOFF2.

The WOFF2 files are the original Google Fonts assets previously emitted by
next/font/google. The italic face comes from:
https://fonts.gstatic.com/s/chakrapetch/v13/cIfnMapbsEk7TDLdtEz1BwkWmpLZRZ_A.ttf

All are loaded with next/font/local in app/layout.tsx, so builds include the
exact files and browsers preload the fonts from the site's own origin.
