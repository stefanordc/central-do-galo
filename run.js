const fs = require('fs');
let c = fs.readFileSync('frontend/src/app/page.tsx', 'utf-8');

c = c.replace(/Cruzeiro/g, 'Galo');

if (!c.includes('abaVideo')) {
  c = c.replace('const [videosYoutube, setVideosYoutube] = useState<VideoYoutube[]>([]);',
    `const [abaVideo, setAbaVideo] = useState<'video' | 'short' | 'live'>('video');
  const [videosYoutube, setVideosYoutube] = useState<VideoYoutube[]>([]);`);
}

const ytOldRegex = /<div className="youtube-home-grid">[\s\S]*?<VideoShelf[\s\S]??variant="live"[\s\S]*?\/>\s*<\/div>/;
const ytNew = `<div className="filters-bar" style={{ marginBottom: '1.5rem', justifyContent: 'center' }}>
  <button type="button" className={\`filter-pill ${abaVideo === 'video' ? 'active' : ''}`} onClick={() => setAbaVideo('video')}>Vídeos</button>
  <button type="button" className={\`filter-pill ${abaVideo === 'short' ? 'active' : ''}`} onClick={() => setAbaVideo('short')}>Shorts</button>
  <button type="button" className={\`filter-pill ${abaVideo === 'live' ? 'active' : ''}`} onClick={() => setAbaVideo('live')}>Ao Vivo</button>
</div>
<div className="youtube-home-grid" style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '20px', alignItems: 'start'}}>
  {(abaVideo === 'video' ? videosYoutube : abaVideo === 'short' ? shortsYoutube : livesYoutube)
    .sort((a, b) => new Date(b.publicado_em || 0).getTime() - new Date(a.publicado_em || 0).getTime())
    .map((video) => (
      <div key={video.id} style={{position: 'relative'}}>
        {video.tipo === 'live' && <div style={{position: 'absolute', top: '10px', right: '10px', backgroundColor: '#e53e3e', color: 'white', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 'bold', zIndex: 10, boxShadow: '0 2px 4px rgba(0,0,0,0.5)'}}>Ao Vivo</div>}
        <VideoCard video={video} onPlay={reproduzirVideo} />
      </div>
    ))}
</div>`;
c = c.replace(ytOldRegex, ytNew);

const xOldRegex = /<div className="x-filter-stack">[\s\S]*?<\/form>\s*<label className="x-profile-filter">[\s\S]??<\/select>\s*<\/label>\s*<\/div>/;
const xNew = `<div className="x-filter-stack filters-bar" style={{ marginBottom: '1.5rem' }}>
  <form className="search-group" onSubmit={pesquisarX} style={{ display: 'flex', gap: '8px', flex: 1 }}>
    <input type="text" className="search-input" placeholder="Ex.: Fred, bastidores, Galo, treino..." value={buscaDigitadaX} onChange={(e) => setBuscaDigitadaX(e.target.value)} />
    <button type="submit" className="search-button">Pesquisar</button>
  </form>
  <div className="select-group">
    <select className="filter-select" value={perfilSelecionadoX} onChange={(e) => setPerfilSelecionadoX(e.target.value)}>
      <option value="">Todos os perfis</option>
      {perfisX.map((conta) => (
        <option value={conta.usuario} key={conta.id}>{conta.nome} (@{conta.usuario})</option>
      ))}
    </select>
  </div>
</div>`;

c = c.replace(xOldRegex, xNew);
fs.writeFileSync('frontend/src/app/page.tsx', c);