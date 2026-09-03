# Central do Galo v30 — Admin

- Timeline do X preservada em páginas de 20 posts.
- Links do HTML oEmbed recebem `target="_blank"` e `rel="noopener noreferrer"` antes da renderização.
- `/admin` não aparece no menu público.
- Login fixo é validado somente pelo backend.
- Admin pode criar páginas públicas em `/p/<slug>`.
- Admin pode cadastrar novos perfis do X; eles entram no job existente de scraping.
- Migration `015_add_admin_pages.sql` cria `public.paginas`.
