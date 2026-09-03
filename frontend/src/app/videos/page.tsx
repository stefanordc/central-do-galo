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
        <Link href="/" style={{color: '#fff', fontSize: '18px', textDecoration: 'none'}}>Notícias</Link>
        <Link href="/videos" style={{color: '#fff', fontSize: '18px', textDecoration: 'none', fontWeight: 'bold'}}>Vím�����1����(������𽹅��(�������͕�ѥ�����屔����������耜��������(���������ā��屔��홽��M��耜�����������]�����耝���������ɝ��	��ѽ�耜��������
���Ʌ�����[��FV�3�����F�b7G��S׷�F�7���vf�W�r�v�s'�r��&v��&�GF�Ӣs#G�w����'WGF����6Ɩ6�ײ����6WD7F�fUF"�wf�FV�r���l:�FV�3��'WGF����'WGF����6Ɩ6�ײ����6WD7F�fUF"�w6��'Br���&VV�3��'WGF�����F�c��F�b7G��S׷�F�7���vw&�Br�w&�EFV��FT6��V��3�w&WVB�WF��f����֖����#��g"��r�v�s#�w����f�FV�2����f�B��������F�b�W�׶��7G��S׷�&�&FW#�s�6�ƖB6662r�FF��s�s�w������7G&��s�f�B�F�F�W���7G&��s������F�c���Т��F�c���6V7F��������������