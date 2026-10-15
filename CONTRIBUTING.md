# Guía de Contribución (CONTRIBUTING.md)

¡Gracias por tu interés en colaborar con **ReVox**! Toda contribución (reporte de bugs, mejoras en la interfaz, documentación o nuevas características) es bienvenida.

---

## 🛠️ Cómo Empezar

1. Hacé un **Fork** del repositorio en GitHub.
2. Cloná tu fork en tu máquina local:
   ```bash
   git clone https://github.com/TU_USUARIO/ReVox-Bot.git
   cd ReVox-Bot
   ```
3. Creá una rama descriptiva para tu cambio:
   ```bash
   git checkout -b feature/nueva-mejora
   ```
4. Configurá el entorno virtual:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   copy .env.example .env
   ```

---

## 🧪 Pruebas Locales

Antes de enviar un Pull Request, verificá que los módulos importen limpiamente:
```powershell
.\.venv\Scripts\python -c "import bot, panel; print('ReVox OK')"
```

Si modificaste la interfaz web (`web/index.html`), probala en el navegador corriendo:
```powershell
.\.venv\Scripts\python panel.py
```

---

## 📝 Estilo de Código y Buenas Prácticas

- **Python:** Código limpio, asíncrono (`asyncio`), tipado cuando aporte claridad y respetando PEP 8.
- **Frontend:** Mantener la estética minimalista y oscura sin añadir librerías pesadas (Tailwind CDN, React o Node.js) para preservar la ligereza del archivo único en HTML/Vanilla JS.
- **Commits:** Mensajes claros siguiendo el formato Conventional Commits (`feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`).

---

## 🚀 Enviar tu Pull Request

1. Asegurate de que no estás incluyendo ningún archivo `.env` o credenciales personales.
2. Hacé push a tu rama en tu fork:
   ```bash
   git push origin feature/nueva-mejora
   ```
3. Abrí un Pull Request en el repositorio principal detallando qué problema resuelve tu cambio y cómo probarlo.
