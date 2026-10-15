# Política de Seguridad (SECURITY.md)

La seguridad y la privacidad de los usuarios son una prioridad en **ReVox**.

## Versiones Soportadas

| Versión | Soportada |
|---|---|
| 1.x (actual) | :white_check_mark: |
| < 1.0 | :x: |

---

## 🔒 Manejo Seguro de Tokens y Credenciales

- **Nunca compartas tu `DISCORD_TOKEN`:** El token del bot otorga acceso total para controlar tu aplicación en Discord.
- El archivo `.env` está expresamente excluido del repositorio mediante `.gitignore`. Si alguna vez subís accidentalmente un token a GitHub, entrá de inmediato a [Discord Developer Portal](https://discord.com/developers/applications) y hacé clic en **Reset Token**.
- ReVox solo se comunica de forma local en tu máquina (`127.0.0.1` / `localhost`). La API web (`5050`) y la conexión a VoiceStudio (`3900`) operan en la interfaz de loopback y no deben ser expuestas públicamente sin túneles con autenticación o proxys inversos seguros.

---

## 🚨 Reporte de Vulnerabilidades

Si descubrís un fallo de seguridad o una vulnerabilidad potencial:

1. **NO abras un Issue público** en GitHub describiendo la vulnerabilidad.
2. Reportalo de forma privada a través de la pestaña de **Security Advisories** del repositorio en GitHub o por correo electrónico al mantenedor.
3. Incluí detalles sobre cómo reproducir el problema y un entorno de prueba si es posible.

Nos comprometemos a responder y evaluar cualquier reporte en un plazo razonable antes de publicar una solución o parche.
