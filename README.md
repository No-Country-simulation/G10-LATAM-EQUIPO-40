# G10-LATAM-EQUIPO-40
Proyecto 2 – 🏥 MediFlow – Agente Autónomo para Triaje, Extracción y Enrutamiento de Documentos Clínicos
## 🖥️ Interfaz de Usuario y Experiencia Clínica (Streamlit)

**Desarrollado por:** Jimmy (Frontend & Conexión) y [Kenia (Diseño UI/UX)]

La interfaz de **MediFlow** fue construida como un panel interactivo de salud (*HealthTech*) sobre **Streamlit**, enfocado en la usabilidad del personal médico y auditores clínicos. Se estructura en tres módulos operativos diseñados para cubrir el ciclo completo de procesamiento y la evaluación del jurado:

---

### 1. Ingesta y Triaje Clínico en Vivo
Módulo de recepción multimodal que permite ingresar documentos mediante subida de archivos (PDF/Imagen) o transcripción de texto directa[cite: 3]. Conecta en tiempo real con el agente autónomo para clasificar la prioridad, identificar entidades clínicas (médico, paciente, diagnóstico CIE-10) y confirmar la persistencia en los buckets de OCI Object Storage Always Free[cite: 3].

![Ingesta y Triaje Clínico](assets/mediflow_ingesta.jpg)
*Captura de la vista de recepción de documentos y clasificación automática en MediFlow.*[cite: 3]

---

### 2. Demostración de Escenarios de Evaluación
Espacio preconfigurado con los tres flujos reglamentarios del Hackathon para permitir una auditoría rápida y repetible durante las presentaciones y el video de entrega[cite: 1]:
* **Caso 1 (Urgencia Crítica):** Tromboembolismo Pulmonar Agudo (TEP) con enrutamiento prioritario a Guardia[cite: 1].
* **Caso 2 (Rutina Ambulatoria):** Receta de tratamiento crónico validada y derivada a Farmacia.
* **Caso 3 (Documento Ambiguo):** Orden médica con datos borrosos o firma ilegible para activación de contingencia.

![Casos de Evaluación Demo](assets/mediflow_casos_demo.jpg)
*Selector interactivo de escenarios de prueba con ejecución determinista.*[cite: 1]

---

### 3. Panel de Auditoría Clínica (Human-in-the-Loop)
Consola de supervisión para el patrón de diseño *Human-in-the-Loop* (HITL)[cite: 2]. Retiene automáticamente cualquier documento cuyo índice de confianza sea inferior a **0.85** o presente inconsistencias estructurales, permitiendo al especialista revisar el motivo de retención, inspeccionar los datos dudosos y autorizar o rechazar el documento con un clic[cite: 2].

![Panel Human-in-the-Loop](assets/mediflow_panel_hitl.jpg)
*Módulo de control de calidad médica para casos derivados a revisión manual.*[cite: 2]

---

### ⚙️ Instrucciones de Ejecución de la UI

Para levantar la interfaz en un entorno local:

```bash
# 1. Clonar el repositorio y ubicarse en la raíz
cd G10-LATAM-EQUIPO-40

# 2. Instalar dependencias del frontend
pip install streamlit

# 3. Iniciar la aplicación
python -m streamlit run app.py
