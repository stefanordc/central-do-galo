'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';

export default function VideosPage() {
  const [activeTab, setActiveTab] = useState('video');
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:8000/api/videos')
      .then(res => res.json())
      .then(data => { setVideos(data); setLoading(false); })
      .catch(err => { console.error(err); setLoading(false); });
  }, []);

  return (
    <main className="page-main">
      <nav style={{display: 'flex', gap: '20px', padding: '20px', background: '#000'}}>
        <Link href="/" style={{color: '#fff', fontSize: '18px', textDecoration: 'none'}}>NotÃ­cias</Link>
        <Link href="/videos" style={{color: '#fff', fontSize: '18px', textDecoration: 'none', fontWeight: 'bold'}}>VÃ­m‘•½Ìð½1¥¹¬ø(€€€€€€ð½¹…Øø(€€€€€€ñÍ•Ñ¥½¸ÍÑå±”õííÁ…‘‘¥¹œè€œÈÁÁàõôø(€€€€€€€€ñ ÄÍÑå±”õíí™½¹ÑM¥é”è€œÈÑÁàœ°™½¹Ñ]•¥¡Ðè€‰½±œ°µ…É¥¹	½ÑÑ½´è€œÈÁÁàõôù•¹ÑÉ…°‘”[µ¶FV÷3Âöƒà¢ÆF—b7G–ÆS×·¶F—7Æ“¢vfÆW‚rÂv¢s'‚rÂÖ&v–ä&÷GFöÓ¢s#G‚w×Óà¢Æ'WGFöâöä6Æ–6³×²‚’Óâ6WD7F—fUF"‚wf–FVòr—Óål:ÖFV÷3Âö'WGFöãà¢Æ'WGFöâöä6Æ–6³×²‚’Óâ6WD7F—fUF"‚w6†÷'Br—Óå&VVÇ3Âö'WGFöãà¢ÂöF—cà¢ÆF—b7G–ÆS×·¶F—7Æ“¢vw&–BrÂw&–EFV×ÆFT6öÇVÖç3¢w&WVB†WFòÖf–ÆÂÂÖ–æÖ‚ƒ#‚Âg"’’rÂv¢s#‚w×Óà¢·f–FV÷2æÖ‚‡f–BÂ’’Óâ€¢ÆF—b¶W“×¶—Ò7G–ÆS×·¶&÷&FW#¢s‚6öÆ–B6662rÂFF–æs¢s‚w×Óà¢ÇãÇ7G&öæsç·f–BçF—FÆWÓÂ÷7G&öæsãÂ÷à¢ÂöF—cà¢’—Ð¢ÂöF—cà¢Â÷6V7F–öãà¢ÂöÖ–ãà¢“°§Ð