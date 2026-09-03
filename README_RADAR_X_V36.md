# Radar do X — v36

Correção do carregamento progressivo do embed nativo do X.

- Mantém timeline, filtro por perfil e paginação de 20 em 20.
- Mantém carregamento escalonado dos embeds para reduzir o pico de rede.
- Remove atualização de estado após o `widgets.js` transformar o blockquote em iframe.
- Evita que o React sobrescreva o iframe nativo do X depois da renderização.
- Mantém o HTML do oEmbed como fallback enquanto o widget ainda não foi montado.
