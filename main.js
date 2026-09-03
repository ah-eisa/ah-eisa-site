const OG_IMAGE = 'https://res.cloudinary.com/dfh3erwx1/image/upload/v1760280190/IMG_0073_vzkxvd.png';

const HEADER_HTML = `
  <div class="header-inner">
    <div class="brand">
      <a href="/index.html" title="Ahmed Eisa - Home"><img src="/assets/icons/ae-logo.svg" alt="AE"></a>
      <div><span class="name">Ahmed Eisa</span><span class="role">Investment Portfolio & Wealth Management</span></div>
    </div>
    <nav class="nav" aria-label="Primary">
      <a href="/index.html">Home</a>
      <a href="/about.html">Profile</a>
      <a href="/experience.html">Experience</a>
      <a href="/projects.html">Selected Work</a>
      <a href="/certifications.html">Credentials</a>
      <a href="/insights.html">Insights</a>
      <a href="/contact.html">Contact</a>
      <a class="nav-cv" href="/assets/pdf/Ahmed_Eisa_Investment_CV.pdf" target="_blank" rel="noopener">Download CV</a>
      <button class="theme-toggle" id="themeToggle" aria-label="Toggle light and dark theme">◐</button>
    </nav>
    <button class="burger" id="burger" aria-label="Open menu">☰</button>
  </div>
  <div class="mobile-menu" id="mobileMenu">
    <a href="/index.html">Home</a><a href="/about.html">Profile</a><a href="/experience.html">Experience</a>
    <a href="/projects.html">Selected Work</a><a href="/certifications.html">Credentials</a><a href="/insights.html">Insights</a>
    <a href="/contact.html">Contact</a><a href="/assets/pdf/Ahmed_Eisa_Investment_CV.pdf" target="_blank" rel="noopener">Download CV</a>
    <button class="theme-toggle" id="themeToggleMobile" aria-label="Toggle light and dark theme">Toggle theme</button>
  </div>`;

const FOOTER_HTML = `
  <div class="footer-inner">
    <div class="footer-left">
      <div class="footer-title">Ahmed Eisa - Investment Portfolio & Wealth Management</div>
      <div>© <span id="year"></span> · Abu Dhabi, UAE</div>
      <div class="footer-avail"><span class="avail-dot"></span>Open to investment leadership opportunities</div>
    </div>
    <div class="footer-links">
      <a href="/privacy.html">Privacy</a><a href="/terms.html">Terms</a><a href="/disclaimer.html">Disclaimer</a>
      <a href="mailto:Ahmed.eisa.2009@gmail.com">Email</a><a href="https://linkedin.com/in/ahmedeisa85" target="_blank" rel="noopener">LinkedIn</a>
    </div>
  </div>`;

(function initShell(){
  const h=document.getElementById('site-header'),f=document.getElementById('site-footer');
  if(h){h.className='site';h.innerHTML=HEADER_HTML} if(f){f.className='site';f.innerHTML=FOOTER_HTML}
  const y=document.getElementById('year'); if(y)y.textContent=new Date().getFullYear();
  const page=window.location.pathname.split('/').pop()||'index.html';
  document.querySelectorAll('.nav a,.mobile-menu a').forEach(a=>{
    const href = a.getAttribute('href');
    if(href === page || href === '/' + page || (page.includes('insights') && href.includes('insights'))) {
      a.classList.add('active');
    }
  });
  function setMeta(prop,content,attr='property'){let el=document.querySelector(`meta[${attr}="${prop}"]`);if(!el){el=document.createElement('meta');el.setAttribute(attr,prop);document.head.appendChild(el)}el.setAttribute('content',content)}
  const title=document.title,desc=document.querySelector('meta[name="description"]')?.content||'';
  setMeta('og:title',title);setMeta('og:description',desc);setMeta('og:image',OG_IMAGE);setMeta('og:type','website');setMeta('og:url',window.location.href);
  setMeta('twitter:card','summary_large_image','name');setMeta('twitter:title',title,'name');setMeta('twitter:description',desc,'name');setMeta('twitter:image',OG_IMAGE,'name');
  const burger=document.getElementById('burger'),mobileMenu=document.getElementById('mobileMenu');
  if(burger&&mobileMenu)burger.addEventListener('click',()=>mobileMenu.classList.toggle('active'));
  const applyTheme=t=>{document.documentElement.setAttribute('data-theme',t);localStorage.setItem('theme',t)};
  applyTheme(localStorage.getItem('theme')||'light');
  const toggle=()=>applyTheme(document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark');
  document.getElementById('themeToggle')?.addEventListener('click',toggle);document.getElementById('themeToggleMobile')?.addEventListener('click',toggle);
})();
