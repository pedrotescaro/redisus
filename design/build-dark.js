const fs = require('fs');
const path = require('path');

const designDir = __dirname;
const darkDir = path.join(designDir, 'dark');

if (!fs.existsSync(darkDir)) {
    fs.mkdirSync(darkDir);
}

// Ensure logo.png is in designDir
// (we already copied it via powershell, assume it's there)

// Get all original HTML files
let files = fs.readdirSync(designDir).filter(f => f.endsWith('.html') && !['settings.html', 'profile.html'].includes(f));

// Let's create settings.html and profile.html based on dashboard.html
const dashboardHtml = fs.readFileSync(path.join(designDir, 'dashboard.html'), 'utf8');

function createPageFromDashboard(title, contentHtml) {
    let newHtml = dashboardHtml;
    newHtml = newHtml.replace('<title>Redisus | Heal+ - Mockup Dashboard</title>', `<title>Redisus | Heal+ - Mockup ${title}</title>`);
    
    // Replace Main Section content
    const mainStart = newHtml.indexOf('<!-- Dashboard Content -->');
    const mainEnd = newHtml.indexOf('</main>');
    if (mainStart !== -1 && mainEnd !== -1) {
        newHtml = newHtml.substring(0, mainStart) + contentHtml + '\n      ' + newHtml.substring(mainEnd);
    }
    return newHtml;
}

const settingsContent = `
      <div class="pt-24 px-8 pb-12 max-w-4xl mx-auto space-y-6">
        <div>
          <h1 class="text-3xl font-extrabold font-headline text-on-surface">Configurações</h1>
          <p class="text-on-surface-variant mt-1">Personalize sua experiência no Heal+</p>
        </div>

        <div class="space-y-6">
          <!-- Aparência -->
          <div class="panel-surface rounded-2xl p-6">
            <div class="flex items-center gap-3 mb-6">
              <div class="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
                <span class="material-symbols-outlined">palette</span>
              </div>
              <div>
                <h3 class="font-bold font-headline text-on-surface">Aparência</h3>
                <p class="text-sm text-on-surface-variant">Escolha o tema visual da interface</p>
              </div>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <a href="{{LIGHT_HREF}}" class="relative overflow-hidden p-4 rounded-2xl transition-all ghost-border {{LIGHT_ACTIVE_CLASS}} block">
                {{LIGHT_BG}}
                <div class="flex flex-col items-center gap-3">
                  <div class="w-12 h-12 rounded-xl flex items-center justify-center {{LIGHT_ICON_BG}}">
                    <span class="material-symbols-outlined text-2xl">light_mode</span>
                  </div>
                  <span class="font-semibold {{LIGHT_TEXT}}">Claro</span>
                </div>
                {{LIGHT_CHECK}}
              </a>

              <a href="{{DARK_HREF}}" class="relative overflow-hidden p-4 rounded-2xl transition-all ghost-border {{DARK_ACTIVE_CLASS}} block">
                {{DARK_BG}}
                <div class="flex flex-col items-center gap-3">
                  <div class="w-12 h-12 rounded-xl flex items-center justify-center {{DARK_ICON_BG}}">
                    <span class="material-symbols-outlined text-2xl">dark_mode</span>
                  </div>
                  <span class="font-semibold {{DARK_TEXT}}">Escuro</span>
                </div>
                {{DARK_CHECK}}
              </a>

              <button class="relative overflow-hidden p-4 rounded-2xl transition-all ghost-border hover:bg-surface-container-high/50 block">
                <div class="flex flex-col items-center gap-3">
                  <div class="w-12 h-12 rounded-xl flex items-center justify-center bg-surface-container text-on-surface-variant">
                    <span class="material-symbols-outlined text-2xl">contrast</span>
                  </div>
                  <span class="font-semibold text-on-surface">Sistema</span>
                </div>
              </button>
            </div>
          </div>

          <!-- Notificações -->
          <div class="panel-surface rounded-2xl p-6">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-10 h-10 rounded-xl bg-tertiary/10 flex items-center justify-center text-tertiary">
                <span class="material-symbols-outlined">notifications</span>
              </div>
              <div>
                <h3 class="font-bold font-headline text-on-surface">Notificações</h3>
                <p class="text-sm text-on-surface-variant">Alertas e lembretes</p>
              </div>
            </div>
            <div class="space-y-3">
              <label class="flex items-center justify-between rounded-xl bg-surface-container p-3">
                <span class="text-sm text-on-surface">Lembretes de agendamento</span>
                <input type="checkbox" checked class="w-4 h-4 text-primary bg-surface-container-high border-outline-variant rounded">
              </label>
              <label class="flex items-center justify-between rounded-xl bg-surface-container p-3">
                <span class="text-sm text-on-surface">Alertas de nova avaliação</span>
                <input type="checkbox" checked class="w-4 h-4 text-primary bg-surface-container-high border-outline-variant rounded">
              </label>
              <label class="flex items-center justify-between rounded-xl bg-surface-container p-3">
                <span class="text-sm text-on-surface">Resumo semanal por e-mail</span>
                <input type="checkbox" class="w-4 h-4 text-primary bg-surface-container-high border-outline-variant rounded">
              </label>
            </div>
          </div>

          <!-- Assistência Inteligente (IA) -->
          <div class="panel-surface rounded-2xl p-6">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
                <span class="material-symbols-outlined">smart_toy</span>
              </div>
              <div>
                <h3 class="font-bold font-headline text-on-surface">Assistência Inteligente (IA)</h3>
                <p class="text-sm text-on-surface-variant">Configure os recursos de Inteligência Artificial</p>
              </div>
            </div>
            <div class="space-y-3">
              <label class="flex items-center justify-between rounded-xl bg-surface-container p-3 cursor-pointer">
                <div>
                  <span class="block text-sm font-bold text-on-surface">Laudos automáticos com IA</span>
                  <span class="block text-xs text-on-surface-variant mt-0.5">Habilitar a geração prévia de resumos clínicos detalhados.</span>
                </div>
                <input type="checkbox" checked class="w-4 h-4 text-primary bg-surface-container-high border-outline-variant rounded">
              </label>
              <label class="flex items-center justify-between rounded-xl bg-surface-container p-3 cursor-pointer">
                <div>
                  <span class="block text-sm font-bold text-on-surface">Diagnóstico Assistido por Imagem</span>
                  <span class="block text-xs text-on-surface-variant mt-0.5">Permite à IA analisar as fotos anexadas às avaliações.</span>
                </div>
                <input type="checkbox" checked class="w-4 h-4 text-primary bg-surface-container-high border-outline-variant rounded">
              </label>
            </div>
          </div>

          <!-- Acessibilidade -->
          <div class="panel-surface rounded-2xl p-6">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-10 h-10 rounded-xl bg-secondary/10 flex items-center justify-center text-secondary">
                <span class="material-symbols-outlined">accessibility_new</span>
              </div>
              <div>
                <h3 class="font-bold font-headline text-on-surface">Acessibilidade</h3>
                <p class="text-sm text-on-surface-variant">Preferências de leitura e navegação</p>
              </div>
            </div>
            <div class="space-y-3">
              <label class="flex items-center justify-between rounded-xl bg-surface-container p-3">
                <span class="text-sm text-on-surface">Texto ampliado</span>
                <input type="checkbox" class="w-4 h-4 text-primary bg-surface-container-high border-outline-variant rounded">
              </label>
              <label class="flex items-center justify-between rounded-xl bg-surface-container p-3">
                <span class="text-sm text-on-surface">Alto contraste</span>
                <input type="checkbox" class="w-4 h-4 text-primary bg-surface-container-high border-outline-variant rounded">
              </label>
              <label class="flex items-center justify-between rounded-xl bg-surface-container p-3">
                <span class="text-sm text-on-surface">Reduzir animacoes</span>
                <input type="checkbox" class="w-4 h-4 text-primary bg-surface-container-high border-outline-variant rounded">
              </label>
            </div>
          </div>

          <!-- Dados & Privacidade -->
          <div class="panel-surface rounded-2xl p-6">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-10 h-10 rounded-xl bg-secondary/10 flex items-center justify-center text-secondary">
                <span class="material-symbols-outlined">security</span>
              </div>
              <div>
                <h3 class="font-bold font-headline text-on-surface">Dados e Privacidade</h3>
                <p class="text-sm text-on-surface-variant">Security e exportacao de dados</p>
              </div>
            </div>
            <p class="text-sm text-on-surface-variant p-4 bg-surface-container rounded-lg">
              Seus dados clinicos permanecem vinculados ao Firebase e as exportacoes ficam no modulo de relatorios.
            </p>
          </div>
        </div>
      </div>
`;
const profileContent = `
      <div class="pt-24 px-8 pb-12 max-w-4xl mx-auto space-y-6">
        <div>
          <h1 class="text-3xl font-extrabold font-headline text-on-surface">Perfil</h1>
          <p class="text-on-surface-variant mt-1">Gerencie suas informações pessoais</p>
        </div>

        <div class="bg-surface-container-low rounded-xl p-8 border border-outline-variant/5">
          <div class="flex flex-col md:flex-row items-start gap-6">
            <div class="w-24 h-24 rounded-full bg-primary/10 flex items-center justify-center text-primary flex-shrink-0 border-4 border-primary-container/20">
              <span class="material-symbols-outlined text-5xl">person</span>
            </div>
            
            <div class="flex-grow">
              <h2 class="text-2xl font-bold font-headline text-on-surface">Profissional de Exemplo</h2>
              <p class="text-on-surface-variant mt-1">profissional@healplus.com</p>
              
              <div class="flex items-center gap-2 mt-3">
                <span class="text-xs font-bold text-primary bg-primary/10 px-3 py-1 rounded-full">
                  Profissional de Saúde
                </span>
                <span class="text-xs font-bold text-tertiary bg-tertiary/10 px-3 py-1 rounded-full flex items-center gap-1">
                  <span class="material-symbols-outlined text-sm">verified</span> Verificado
                </span>
              </div>
              
              <div class="mt-4 flex items-center gap-3">
                <label class="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-surface-container-high px-3 py-2 text-sm hover:brightness-95 transition-all text-on-surface">
                  <span class="material-symbols-outlined text-base">photo_camera</span>
                  Trocar foto
                </label>
              </div>
            </div>
          </div>

          <div class="mt-8 pt-8 border-t border-outline-variant/10 grid gap-6 md:grid-cols-2">
            <div>
              <p class="text-xs font-bold uppercase tracking-wider text-outline mb-2">ID da Conta</p>
              <p class="text-on-surface font-mono text-sm bg-surface-container-high px-4 py-2 rounded-lg">
                12345abcdef...
              </p>
            </div>
            <div>
              <p class="text-xs font-bold uppercase tracking-wider text-outline mb-2">Último Login</p>
              <p class="text-on-surface text-sm bg-surface-container-high px-4 py-2 rounded-lg">
                24 de março de 2026 às 14:00
              </p>
            </div>
          </div>

          <div class="mt-8 pt-8 border-t border-outline-variant/10 space-y-4">
            <p class="text-xs font-bold uppercase tracking-wider text-outline">Editar perfil</p>
            <div class="grid gap-3 md:grid-cols-[1fr_auto]">
              <input type="text" value="Profissional de Exemplo" class="flex h-10 w-full rounded-md border border-outline-variant/20 bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 text-on-surface" placeholder="Digite seu nome de exibicao">
              <button class="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-on-primary hover:bg-primary/90 h-10 px-4 py-2">
                Salvar nome
              </button>
            </div>
          </div>
        </div>

        <section class="bg-surface-container-low rounded-xl p-6 border border-outline-variant/10">
          <h3 class="text-xl font-bold font-headline text-on-surface">Preferencias da conta</h3>
          <p class="text-on-surface-variant text-sm mt-1 mb-4">
            Configure notificacoes e acessibilidade na pagina de configuracoes.
          </p>
          <a href="settings.html" class="inline-flex items-center justify-center rounded-md text-sm font-medium border border-outline-variant/20 bg-transparent hover:bg-surface-container-high h-10 px-4 py-2 text-on-surface">
            Ir para Configuracoes
          </a>
        </section>
      </div>
`;

fs.writeFileSync(path.join(designDir, 'settings.html'), createPageFromDashboard('Configurações', settingsContent));
fs.writeFileSync(path.join(designDir, 'profile.html'), createPageFromDashboard('Perfil', profileContent));

// Now re-read all text files including newly created ones
files = fs.readdirSync(designDir).filter(f => f.endsWith('.html'));

const lightLogoRegex = /<div class="w-(12|14) h-(12|14)[^>]*?>Logo<\/div>/g;

for (const file of files) {
    let content = fs.readFileSync(path.join(designDir, file), 'utf8');
    
    // Replace text logo with image for light mode (src="logo.png")
    const imgTagLight = `<img src="logo.png" alt="Heal+ Logo" class="h-10 w-auto transition-transform group-hover:scale-105 object-contain">`;
    content = content.replace(lightLogoRegex, imgTagLight);
    
    // Since settings and profile have href="#" for Settings in sidebar in dashboard, let's fix the links
    content = content.replace(/href="#" class="flex items-center gap-3 px-4 py-3 text-on-surface-variant hover:text-on-surface transition-colors font-medium hover:bg-primary\/5 rounded-lg">\s*<span class="material-symbols-outlined">settings<\/span>/g, 'href="settings.html" class="flex items-center gap-3 px-4 py-3 text-on-surface-variant hover:text-on-surface transition-colors font-medium hover:bg-primary/5 rounded-lg">\n          <span class="material-symbols-outlined">settings</span>');
    
    // Add Profile to Sidebar Main Navigation (under Assistente IA)
    // Add Profile to Sidebar Main Navigation (under Assistente IA)
    // First, let's remove the old profile link everywhere in the sidebar to clean up corrupted files
    content = content.replace(/<a href="profile\.html" class="[^"]* items-center gap-3[^>]*>\s*<span class="material-symbols-outlined">person<\/span>\s*<span>Perfil<\/span>\s*<\/a>\s*/g, '');

    const profileLink = '\n        <a href="profile.html" class="relative flex items-center gap-3 mx-4 px-4 py-3 transition-all font-medium rounded-xl text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low">\n            <span class="material-symbols-outlined">person</span>\n            <span>Perfil</span>\n        </a>';
    
    // We search for the Assistente IA link closure specifically!
    content = content.replace(/(<span>Assistente IA<\/span>\s*<\/a>)/g, '$1' + profileLink);

    // Replace Sair button with simple styled login redirect link (revert original look)
    content = content.replace(/<a href="login\.html" class="w-full mt-2 flex items-center justify-center gap-2 rounded-xl bg-error\/10 px-4 py-3 text-sm font-bold text-error border border-error\/20 transition-all hover:bg-error hover:text-white hover:border-error shadow-sm hover:shadow-ambient dark:hover:bg-error-container dark:hover:text-on-error-container dark:hover:border-error-container">[\s\S]*?<span class="material-symbols-outlined text-\[20px\]">logout<\/span>[\s\S]*?<span>Sair do Sistema<\/span>[\s\S]*?<\/a>/, 
    '<a href="login.html" class="w-full flex items-center gap-3 px-4 py-3 text-error hover:text-error transition-colors font-medium hover:bg-error/10 rounded-lg">\n          <span class="material-symbols-outlined">logout</span>\n          <span>Sair</span>\n        </a>');

    // Also handle case where it hasn't been built yet and still has the <button>
    content = content.replace(/<button class="w-full flex items-center gap-3 px-4 py-3 text-error hover:text-error transition-colors font-medium hover:bg-error\/10 rounded-lg">[\s\S]*?<span class="material-symbols-outlined">logout<\/span>[\s\S]*?<span>Sair<\/span>[\s\S]*?<\/button>/, 
    '<a href="login.html" class="w-full flex items-center gap-3 px-4 py-3 text-error hover:text-error transition-colors font-medium hover:bg-error/10 rounded-lg">\n          <span class="material-symbols-outlined">logout</span>\n          <span>Sair</span>\n        </a>');

    content = content.replace(/<div class="flex items-center gap-3 cursor-pointer hover:opacity-80 transition-opacity">/g, '<a href="profile.html" class="flex items-center gap-3 cursor-pointer hover:opacity-80 transition-opacity">');
    // We should close the anchor tag for profile, but let's just do a simple replacement
    content = content.replace(/<div class="w-10 h-10 rounded-full border-2 border-outline-variant\/20 bg-surface-container flex items-center justify-center">\s*<span class="material-symbols-outlined text-on-surface-variant">person<\/span>\s*<\/div>\s*<\/div>/, '<div class="w-10 h-10 rounded-full border-2 border-outline-variant/20 bg-surface-container flex items-center justify-center">\n              <span class="material-symbols-outlined text-on-surface-variant">person</span>\n            </div>\n          </a>');

    // 1. Remove ALL active markers first
    content = content.replace(/class="relative flex items-center gap-3 mx-4 px-4 py-3 transition-all font-medium rounded-xl text-on-primary-container shadow-ambient" style="background: linear-gradient\(15deg, var\(--primary\) 0%, #2196f3 100%\);"/g, 'class="relative flex items-center gap-3 mx-4 px-4 py-3 transition-all font-medium rounded-xl text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low"');
    content = content.replace(/<span class="absolute left-0 top-2 bottom-2 w-1 rounded-full bg-surface-container-lowest"><\/span>\s*/g, '');
    content = content.replace(/<span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1;">/g, '<span class="material-symbols-outlined">');
    
    // Bottom nav uses slightly different inactive class, make sure it is inactive too (though it normally is)
    content = content.replace(/class="flex items-center gap-3 px-4 py-3 text-on-primary-container shadow-ambient" style="background: linear-gradient\(15deg, var\(--primary\) 0%, #2196f3 100%\);"/g, 'class="flex items-center gap-3 px-4 py-3 text-on-surface-variant hover:text-on-surface transition-colors font-medium hover:bg-primary/5 rounded-lg"');

    // 2. Set active marker for the CURRENT file
    // For main nav
    let activeMainClass = 'class="relative flex items-center gap-3 mx-4 px-4 py-3 transition-all font-medium rounded-xl text-on-primary-container shadow-ambient" style="background: linear-gradient(15deg, var(--primary) 0%, #2196f3 100%);"';
    let inactiveMainRegex = new RegExp(`<a href="${file}" class="relative flex items-center gap-3 mx-4 px-4 py-3 transition-all font-medium rounded-xl text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low">\\s*<span class="material-symbols-outlined">([^<]+)<\\/span>`, 'g');
    content = content.replace(inactiveMainRegex, `<a href="${file}" ${activeMainClass}>\n            <span class="absolute left-0 top-2 bottom-2 w-1 rounded-full bg-surface-container-lowest"></span>\n            <span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1;">$1</span>`);

    // For bottom nav (e.g. settings)
    let activeBottomClass = 'class="flex items-center gap-3 px-4 py-3 text-on-primary-container shadow-ambient rounded-lg" style="background: linear-gradient(15deg, var(--primary) 0%, #2196f3 100%);"';
    let inactiveBottomRegex = new RegExp(`<a href="${file}" class="flex items-center gap-3 px-4 py-3 text-on-surface-variant hover:text-on-surface transition-colors font-medium hover:bg-primary\\/5 rounded-lg">\\s*<span class="material-symbols-outlined">([^<]+)<\\/span>`, 'g');
    content = content.replace(inactiveBottomRegex, `<a href="${file}" ${activeBottomClass}>\n          <span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1;">$1</span>`);

    // Add missing surface-container-high to tailwind config
    if (!content.includes('"surface-container-high":')) {
      content = content.replace(
        '"surface-container-low": "var(--surface-container-low)", "surface-container": "var(--surface-container)",',
        '"surface-container-low": "var(--surface-container-low)", "surface-container": "var(--surface-container)", "surface-container-high": "var(--surface-container-high)",'
      );
    }

    // Render Settings Theme Buttons for LIGHT mode
    let lightModeContent = content;
    lightModeContent = lightModeContent.replace('{{LIGHT_HREF}}', 'settings.html');
    lightModeContent = lightModeContent.replace('{{LIGHT_ACTIVE_CLASS}}', 'bg-primary/10');
    lightModeContent = lightModeContent.replace('{{LIGHT_BG}}', '<div class="absolute inset-0 bg-gradient-to-br from-white/45 to-primary/5 pointer-events-none"></div>');
    lightModeContent = lightModeContent.replace('{{LIGHT_ICON_BG}}', 'bg-primary-container text-on-primary-container shadow-ambient');
    lightModeContent = lightModeContent.replace('{{LIGHT_TEXT}}', 'text-primary');
    lightModeContent = lightModeContent.replace('{{LIGHT_CHECK}}', '<div class="absolute top-2 right-2"><span class="material-symbols-outlined text-primary text-sm">check_circle</span></div>');
    
    lightModeContent = lightModeContent.replace('{{DARK_HREF}}', 'dark/settings.html');
    lightModeContent = lightModeContent.replace('{{DARK_ACTIVE_CLASS}}', 'hover:bg-surface-container-high/50');
    lightModeContent = lightModeContent.replace('{{DARK_BG}}', '');
    lightModeContent = lightModeContent.replace('{{DARK_ICON_BG}}', 'bg-surface-container text-on-surface-variant');
    lightModeContent = lightModeContent.replace('{{DARK_TEXT}}', 'text-on-surface');
    lightModeContent = lightModeContent.replace('{{DARK_CHECK}}', '');

    // Save light version back
    fs.writeFileSync(path.join(designDir, file), lightModeContent);

    // Create dark version
    let darkContent = content;
    // Dark mode HTML tag
    darkContent = darkContent.replace(/<html ([^>]*)class="[^"]*"([^>]*)>/, '<html $1class="dark"$2>');
    if (!darkContent.includes('class="dark"')) {
        // If it didn't have a class tag
        darkContent = darkContent.replace(/<html /, '<html class="dark" ');
    }
    
    // Fix src for logo and styles.css
    darkContent = darkContent.replace(/src="logo\.png"/g, 'src="../logo.png"');
    darkContent = darkContent.replace(/href="styles\.css"/g, 'href="../styles.css"');
    
    // Render Settings Theme Buttons for DARK mode
    darkContent = darkContent.replace('{{LIGHT_HREF}}', '../settings.html');
    darkContent = darkContent.replace('{{LIGHT_ACTIVE_CLASS}}', 'hover:bg-surface-container-high/50');
    darkContent = darkContent.replace('{{LIGHT_BG}}', '<div class="absolute inset-0 bg-gradient-to-br from-white/45 to-primary/5 pointer-events-none"></div>');
    darkContent = darkContent.replace('{{LIGHT_ICON_BG}}', 'bg-surface-container text-on-surface-variant');
    darkContent = darkContent.replace('{{LIGHT_TEXT}}', 'text-on-surface');
    darkContent = darkContent.replace('{{LIGHT_CHECK}}', '');
    
    darkContent = darkContent.replace('{{DARK_HREF}}', 'settings.html');
    darkContent = darkContent.replace('{{DARK_ACTIVE_CLASS}}', 'bg-primary/10');
    darkContent = darkContent.replace('{{DARK_BG}}', '<div class="absolute inset-0 bg-gradient-to-br from-primary/15 via-transparent to-surface-container-high/80 pointer-events-none"></div>');
    darkContent = darkContent.replace('{{DARK_ICON_BG}}', 'bg-primary-container text-on-primary-container shadow-ambient');
    darkContent = darkContent.replace('{{DARK_TEXT}}', 'text-primary');
    darkContent = darkContent.replace('{{DARK_CHECK}}', '<div class="absolute top-2 right-2"><span class="material-symbols-outlined text-primary text-sm">check_circle</span></div>');

    // Also links to other html files should probably just stay same (they will link to dark/xxx.html)

    // Specifically handle the dark mode theme toggle link in headers (like in login.html and index.html)
    let headerToggleRegex = new RegExp(`<a href="dark\\/${file}" title="Alternar tema" class="bg-surface-container-low rounded-full p-2 flex text-on-surface-variant hover:text-on-surface shadow-ambient transition-all">\\s*<span class="material-symbols-outlined text-\\[20px\\]">dark_mode<\\/span>\\s*<\\/a>`);
    let headerToggleReplacement = `<a href="../${file}" title="Alternar tema" class="bg-surface-container-low rounded-full p-2 flex text-on-surface-variant hover:text-on-surface shadow-ambient transition-all">\n          <span class="material-symbols-outlined text-[20px]">light_mode</span>\n        </a>`;
    darkContent = darkContent.replace(headerToggleRegex, headerToggleReplacement);

    fs.writeFileSync(path.join(darkDir, file), darkContent);
}

console.log("Done generating files.");
