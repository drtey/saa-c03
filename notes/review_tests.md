## Amazon S3 Notifications + SNS Fanout Pattern

### ¿Cómo funcionan las notificaciones en S3?

Cuando ocurre un evento en tu bucket (subida de archivo, eliminación, etc.), S3 puede **notificar automáticamente** a un destino. Los destinos soportados son:

```
S3 Bucket  →  SNS Topic
           →  SQS Queue
           →  Lambda Function
```

⚠️ **Limitación crítica:** S3 solo puede enviar la notificación a **un único destino** a la vez.

---

### El problema del escenario

Tienes una notificación S3 que ya va a una SQS queue, pero ahora necesitas que **dos equipos** (desarrollo y operaciones) reciban esa notificación.

❌ **Solución ingenua (incorrecta):** Agregar una segunda SQS queue directamente en S3.
> No es posible. S3 solo admite un destino por evento.

✅ **Solución correcta:** Usar el patrón **Fanout con SNS**.

---

### El patrón Fanout

La idea es usar SNS como intermediario que **multiplica** el mensaje hacia varios suscriptores:

```
                          ┌──→ SQS Queue A (equipo de desarrollo)
S3 Bucket → SNS Topic ───┤
                          └──→ SQS Queue B (equipo de operaciones)
```

Cuando S3 publica el evento en el SNS Topic, SNS se encarga de replicarlo y enviarlo a **todas las colas suscritas simultáneamente** (procesamiento paralelo y asíncrono).

---

### ¿Por qué las otras opciones están mal?

**❌ Agregar una segunda SQS queue directamente en S3**
> S3 no soporta múltiples destinos para el mismo evento. Solo puedes tener 1 SQS o 1 SNS configurado a la vez.

**❌ Crear un segundo SNS Topic FIFO para el otro equipo**
> Mismo problema: no puedes tener dos destinos en S3. Además, FIFO no es necesario aquí. SNS FIFO + SQS FIFO se usan cuando necesitas **orden estricto de mensajes y deduplicación**, lo cual no aplica en este caso.

**❌ Configurar las SQS queues para "hacer polling" al SNS Topic**
> Esto revela una confusión conceptual importante:

| Servicio | Modelo de entrega |
|---|---|
| **SQS** | Pull/Polling — tú consultas la cola para obtener mensajes |
| **SNS** | Push — SNS empuja el mensaje a los suscriptores |

> Las colas SQS deben **suscribirse** al topic SNS, no hacer polling. SNS nunca es consultado; él entrega activamente.

---

### Solución paso a paso

1. **Crear un SNS Topic** (estándar, no FIFO)
2. **Crear dos SQS queues** y suscribirlas al topic
3. **Dar permisos a S3** para publicar en SNS
4. **Actualizar el bucket** para que envíe notificaciones al nuevo SNS Topic

Así, con un solo destino desde S3, logras que el mensaje llegue a múltiples consumidores.

&nbsp;


&nbsp;


&nbsp;

## Amazon Aurora: Endpoints y Conexiones

### ¿Qué es Aurora y por qué usa endpoints?

Aurora no es una sola instancia de base de datos, sino un **cluster** (grupo) de instancias. Para no obligarte a recordar las IPs/hostnames de cada instancia ni programar tu propia lógica de conexión, Aurora usa **endpoints**: direcciones intermediarias que apuntan automáticamente a la instancia correcta.

---

### Tipos de Endpoints

| Endpoint | También llamado | ¿A dónde apunta? | Uso típico |
|---|---|---|---|
| **Cluster endpoint** | Writer endpoint | Instancia primaria (lectura/escritura) | DDL, DML, operaciones de escritura |
| **Reader endpoint** | — | Reparte carga entre todas las réplicas | Consultas de solo lectura |
| **Custom endpoint** | — | Subconjunto específico de instancias | Casos de uso especializados |
| **Instance endpoint** | — | Una instancia específica | Diagnóstico, tuning |

---

### El concepto clave: Custom Endpoints

El texto resuelve este escenario: **tienes instancias de alta y baja capacidad, y quieres separar el tráfico de producción del de reportes.**

```
Tráfico de producción  →  Custom Endpoint A  →  Instancias de ALTA capacidad
Consultas de reportes  →  Custom Endpoint B  →  Instancias de BAJA capacidad
```

Esto es posible porque un **custom endpoint** te permite agrupar instancias según criterios propios, como:
- Clase de instancia (`db.r5.4xlarge` vs `db.t3.medium`)
- Grupo de parámetros específico
- Cualquier subconjunto lógico que definas

---

### ¿Por qué las otras opciones están mal?

**❌ Solo usar el reader endpoint para todo**
> El reader endpoint solo balancea carga entre réplicas, pero no distingue entre instancias de alta o baja capacidad. No cumple el requisito de separar cargas por capacidad.

**❌ Cluster endpoint para producción + reader endpoint para reportes**
> El cluster endpoint apunta a la instancia primaria (escritura). No dirige a instancias de alta capacidad específicas, y mezclar endpoints sin criterio de capacidad no resuelve el problema.

**❌ No hacer nada, Aurora lo hace automáticamente**
> Aurora **no** separa tráfico por capacidad de forma automática. Eso es responsabilidad tuya mediante custom endpoints.

---

### Resumen mental

Piensa en los endpoints como **recepcionistas especializados**:
- El *writer* siempre te manda al jefe (instancia primaria).
- El *reader* te manda a cualquier asistente disponible (réplicas).
- El *custom* te manda exactamente al equipo que tú configuraste previamente.

&nbsp;


&nbsp;


&nbsp;

## Seguridad de Variables de Entorno en AWS Lambda

### ¿Cómo funciona el cifrado en Lambda por defecto?

Cuando creas una función Lambda con variables de entorno, AWS **automáticamente las cifra** usando KMS. Pero hay un detalle importante:

```
Cifrado por defecto (KMS key por defecto)
├── ✅ Los valores están cifrados en reposo
└── ❌ Siguen siendo VISIBLES en texto plano en la consola Lambda
         para cualquier usuario con acceso
```

Este es el problema central del escenario: **cifrado ≠ privacidad en la consola**.

---

### La solución: KMS key propia + Encryption Helpers

Al crear tu propia KMS key y usar los **encryption helpers** de Lambda:

```
Tu KMS Key propia
├── ✅ Datos cifrados en reposo
├── ✅ Valores NO visibles en texto plano en la consola
├── ✅ Tú controlas quién tiene acceso a la key
├── ✅ Puedes rotar, deshabilitar y auditar la key
└── ✅ Puedes definir controles de acceso granulares
```

---

### Comparación de opciones

| Opción | Veredicto | Razón |
|---|---|---|
| "Lambda ya cifra por defecto, no hay que hacer nada" | ❌ | El cifrado por defecto existe, pero los valores siguen visibles en la consola para otros usuarios |
| "Crear una KMS key propia y usar encryption helpers" | ✅ | Máxima seguridad: cifrado real + acceso controlado + invisible en consola |
| "Usar SSL con CloudHSM" | ❌ | SSL solo cifra datos **en tránsito**, no en reposo. Los valores seguirían visibles |
| "Lambda no cifra, usar EC2" | ❌ | Falso. Lambda sí cifra variables de entorno |

---

### La distinción clave que evalúa este examen

```
Cifrado por defecto (default KMS key)
│
├── Protege los datos en disco ✅
└── Pero cualquier usuario con acceso a la consola
    puede VER los valores → No es suficiente ❌

Cifrado con KMS key propia + Encryption Helpers
│
├── Protege los datos en disco ✅
└── Los valores aparecen CIFRADOS incluso en la consola ✅
    Solo quien tenga permiso sobre esa KMS key puede descifrarlos
```

---

### Regla mental para el examen

> Cuando el requisito sea **máxima seguridad** para variables sensibles en Lambda → siempre elige **KMS key propia + encryption helpers**, no la key por defecto.

La key por defecto es conveniente, pero la key propia te da **control total**: crear, rotar, deshabilitar, auditar y restringir acceso.

&nbsp;


&nbsp;


&nbsp;

## Almacenamiento Hot vs Cold para ML en AWS

### Clasificación del almacenamiento por temperatura

```
HOT   → Datos frecuentemente accedidos → Alto rendimiento, mayor costo
WARM  → Datos ocasionalmente accedidos → Balance rendimiento/costo
COLD  → Datos raramente accedidos      → Bajo rendimiento, mínimo costo
```

---

### Los dos requisitos del escenario

| Requisito | Característica clave | Servicio correcto |
|---|---|---|
| Hot storage | Alto rendimiento + **paralelo** + concurrente | **Amazon FSx for Lustre** |
| Cold storage | **Costo-efectivo** + archivado | **Amazon S3 (Glacier)** |

---

### ¿Por qué FSx for Lustre para hot storage?

Lustre es un sistema de archivos **paralelo y distribuido** (open-source) que:
- Divide los datos entre múltiples servidores de red simultáneamente
- Elimina cuellos de botella en workloads de alto procesamiento
- Es el estándar de facto para **Machine Learning y HPC** (High Performance Computing)

```
Dataset → FSx for Lustre → Múltiples nodos procesan en paralelo
                           └── Nodo 1, Nodo 2, Nodo 3... (concurrente)
```

### ¿Por qué S3 para cold storage?

S3 ofrece una jerarquía de almacenamiento que lo hace ideal para datos fríos:

```
S3 Standard          → Hot data
S3 Standard-IA       → Warm data
S3 Glacier           → Cold data    ← aplica aquí
S3 Glacier Deep Archive → Coldest   ← o aquí (más barato aún)
```

---

### Por qué las otras opciones fallan

**❌ FSx for Lustre + EBS Provisioned IOPS (io1)**
> EBS io1 está diseñado para hot data de I/O intensivo, no para archivado frío. El EBS Cold HDD existe, pero es significativamente más caro que S3 Glacier, por lo que no cumple el requisito de "cost-effective".

**❌ Amazon EFS + S3**
> EFS sí permite acceso concurrente, pero **no tiene sistema de archivos paralelo**. Para workloads de ML que necesitan máximo rendimiento, EFS no es suficiente. FSx for Lustre lo supera ampliamente en performance.

**❌ FSx for Windows File Server + S3**
> FSx for Windows usa protocolo **SMB + NTFS**, diseñado para entornos Windows empresariales. No tiene arquitectura de sistema de archivos paralelo como Lustre.

---

### Regla mental para el examen

> - "Alto rendimiento + paralelo + ML/HPC" → **FSx for Lustre**
> - "Windows + Active Directory + SMB" → **FSx for Windows**
> - "Archivado barato + cold storage" → **S3 Glacier / Glacier Deep Archive**
> - "Almacenamiento compartido general en la nube" → **EFS**

&nbsp;


&nbsp;


&nbsp;
## RDS Multi-AZ Failover: Alta Disponibilidad ante Fallos de Zona

### El problema del escenario

La base de datos existe en **una sola Availability Zone**. Si esa zona falla → acceso perdido completamente. La solución es eliminar ese único punto de fallo.

---

### ¿Qué hace Multi-AZ?

```
AZ-A (primaria)          AZ-B (standby)
┌─────────────┐          ┌─────────────┐
│  RDS Primary │──sync──→│  RDS Standby│
│  (activa)    │          │  (en espera)│
└─────────────┘          └─────────────┘
       ↕ replicación síncrona
  Si AZ-A falla → RDS promueve automáticamente el standby
  Sin intervención manual → mínimo downtime
```

Características clave:
- Replicación **síncrona** → consistencia total de datos
- Failover **automático** → sin intervención manual
- El standby está en infraestructura **físicamente separada**
- Cubre: fallos de AZ, mantenimiento planificado, fallos de hardware

---

### Por qué las otras opciones no resuelven el problema

| Opción | Propósito real | ¿Previene pérdida de acceso? |
|---|---|---|
| **Snapshot** | Backup / recuperación puntual | ❌ Debes restaurar manualmente, hay downtime |
| **Aumentar tamaño de instancia** | Más CPU/RAM → mejor performance | ❌ Sigue en la misma AZ, mismo punto de fallo |
| **Read Replica** | Escalar lecturas | ❌ Promoción a instancia principal es **manual** |
| **Multi-AZ Failover** | Alta disponibilidad | ✅ Failover automático a otra AZ |

---

### La distinción crítica: Read Replica vs Multi-AZ

Es la confusión más común en el examen:

```
Read Replica                    Multi-AZ Standby
────────────────                ────────────────
Replicación ASÍNCRONA           Replicación SÍNCRONA
Sirve tráfico de lectura        NO sirve tráfico (solo espera)
Failover MANUAL                 Failover AUTOMÁTICO
Escala performance              Garantiza disponibilidad
```

> **Regla:** Si el requisito menciona *"alta disponibilidad"*, *"failover automático"* o *"evitar downtime ante fallos"* → siempre **Multi-AZ**.

&nbsp;


&nbsp;


&nbsp;

## Amazon Macie: Protección de Datos Sensibles en S3

### ¿Qué es Amazon Macie?

Es un servicio de seguridad **impulsado por Machine Learning** que automáticamente:
- **Descubre** datos sensibles en S3
- **Clasifica** la información (PII, propiedad intelectual, etc.)
- **Monitorea** políticas de privacidad y seguridad en buckets
- **Alerta** sobre violaciones potenciales

---

### Los dos tipos de hallazgos (findings) que genera Macie

```
Policy Findings                     Sensitive Data Findings
───────────────                     ───────────────────────
Violaciones de política             Datos sensibles encontrados
Problemas de seguridad/privacidad   en objetos S3 específicos
en buckets S3                       
Monitoreo continuo y automático     Requiere configurar un
                                    "sensitive data discovery job"
```

Ambos requisitos del escenario están cubiertos:
- ✅ Verificar datos con PII → **Sensitive Data Findings**
- ✅ Alertar sobre violaciones de privacidad → **Policy Findings**

---

### Los otros servicios y por qué no aplican

| Servicio | Para qué sirve realmente | ¿Aplica al escenario? |
|---|---|---|
| **Amazon Polly** | Convierte texto en voz (text-to-speech) | ❌ No tiene relación con seguridad |
| **Amazon Kendra** | Búsqueda empresarial con IA | ❌ Busca contenido, no monitorea seguridad |
| **Amazon Fraud Detector** | Detecta fraudes en transacciones online | ❌ No analiza PII en S3 |
| **Amazon Macie** | Descubre y protege datos sensibles en S3 | ✅ Exactamente esto |

---

### Regla mental para el examen

> Siempre que veas estas palabras juntas en una pregunta → piensa en **Macie**:
> - PII (Personally Identifiable Information)
> - Datos sensibles en S3
> - Compliance / políticas de privacidad
> - Clasificación automática de datos
> - Alertas de seguridad sobre buckets S3

 &nbsp;   
 
 &nbsp;   
 
 &nbsp;

## Aurora MySQL Native Functions + Lambda: Reacción a Cambios de Datos

### El concepto clave: RDS Events vs. Database Events

Esta es la trampa central de la pregunta:

```
RDS Event Subscriptions          Aurora Native Functions
───────────────────────          ───────────────────────
Eventos de INFRAESTRUCTURA       Eventos de DATOS
├── Failover                     ├── INSERT
├── Mantenimiento                ├── UPDATE
├── Backup completado            └── DELETE  ← aplica aquí
└── Cambio de parámetros
❌ NO detecta DELETE de filas    ✅ SÍ detecta cambios en datos
```

---

### La solución correcta paso a paso

```
1. Vehículo vendido
       ↓
2. DELETE en tabla Aurora MySQL
       ↓
3. Native function (lambda_sync / lambda_async) dispara automáticamente
       ↓
4. AWS Lambda recibe los datos del listing eliminado
       ↓
5. Lambda envía datos a SQS Queue
       ↓
6. Sistema distribuido consume el mensaje de SQS
```

Aurora MySQL ofrece dos funciones nativas para invocar Lambda:

| Función | Comportamiento |
|---|---|
| `lambda_sync` | Invocación **síncrona** → espera respuesta de Lambda |
| `lambda_async` | Invocación **asíncrona** → no espera respuesta |

---

### Por qué las 3 opciones con "RDS Event Subscription" están mal

Las tres opciones incorrectas comparten el mismo error fundamental: usan **RDS Event Subscriptions**, que solo capturan eventos operacionales/infraestructura, **nunca cambios en los datos** como un `DELETE` en una tabla.

| Opción incorrecta | Error adicional |
|---|---|
| RDS Events → SNS → SQS → Lambda | RDS Events no captura `DELETE` de filas |
| RDS Events → SQS → SNS → Lambda | Mismo problema + el fanout va en dirección incorrecta (SQS no hace fanout a SNS) |
| RDS Events → Lambda → SQS | Mismo problema de raíz |

---

### Regla mental para el examen

> - Reaccionar a **cambios en datos** (INSERT/UPDATE/DELETE) en Aurora MySQL → **Native Functions** (`lambda_sync`/`lambda_async`)
> - Reaccionar a **eventos de infraestructura** RDS (failover, backup, mantenimiento) → **RDS Event Subscriptions**
 
 &nbsp;   
 
 &nbsp;   
 
 &nbsp;

## RDS Enhanced Monitoring: Visibilidad Granular del Sistema Operativo

### El problema central del escenario

Se necesita monitorear **por proceso/thread** el uso de CPU y memoria. Esto requiere visibilidad a nivel de sistema operativo, no solo métricas agregadas.

---

### CloudWatch estándar vs Enhanced Monitoring

```
CloudWatch estándar              Enhanced Monitoring
───────────────────              ───────────────────
Datos del HIPERVISOR             Datos del AGENTE en la instancia
Vista agregada de la VM          Vista granular del OS
CPU total de la instancia        CPU por proceso/thread individual
Menos preciso en instancias      Más preciso y detallado
pequeñas (comparten hipervisor)  independiente del hipervisor
```

Enhanced Monitoring responde exactamente al requisito:
- ✅ % de CPU por cada proceso
- ✅ Memoria total consumida por cada proceso
- ✅ Métricas en tiempo real
- ✅ Datos retenidos 30 días en CloudWatch Logs (ajustable)

---

### Por qué las otras opciones fallan

| Opción | Por qué no cumple el requisito |
|---|---|
| **CPU% y MEM% en consola RDS** | Esas métricas **no están disponibles** directamente en la consola RDS como lo describe la opción |
| **CloudWatch estándar** | Solo ve CPU agregada desde el hipervisor, no por proceso individual |
| **Script custom → CloudWatch** | No tienes acceso directo al OS de RDS (a diferencia de EC2). No puedes instalar agentes o scripts personalizados |

---

### El punto clave sobre RDS vs EC2

```
EC2                              RDS
───                              ───
✅ Acceso al OS                  ❌ Sin acceso directo al OS
✅ Puedes instalar agentes        ❌ No puedes instalar scripts
✅ Custom CloudWatch agent        ✅ Enhanced Monitoring (agente
                                    gestionado por AWS)
```

> En RDS, AWS gestiona el OS por ti. Por eso la única forma de obtener métricas a nivel de proceso es mediante **Enhanced Monitoring**, que usa un agente que AWS instala y administra automáticamente.

---

### Regla mental para el examen

> - Monitorear **procesos/threads individuales** en RDS → **Enhanced Monitoring**
> - Monitorear **métricas generales** de la instancia RDS → **CloudWatch**
> - Monitorear **queries lentas o rendimiento SQL** → **RDS Performance Insights**
 
 &nbsp;   
 
 &nbsp;   
 
 &nbsp;

## RDS Enhanced Monitoring: Visibilidad Granular del Sistema Operativo

### El problema central del escenario

Se necesita monitorear **por proceso/thread** el uso de CPU y memoria. Esto requiere visibilidad a nivel de sistema operativo, no solo métricas agregadas.

---

### CloudWatch estándar vs Enhanced Monitoring

```
CloudWatch estándar              Enhanced Monitoring
───────────────────              ───────────────────
Datos del HIPERVISOR             Datos del AGENTE en la instancia
Vista agregada de la VM          Vista granular del OS
CPU total de la instancia        CPU por proceso/thread individual
Menos preciso en instancias      Más preciso y detallado
pequeñas (comparten hipervisor)  independiente del hipervisor
```

Enhanced Monitoring responde exactamente al requisito:
- ✅ % de CPU por cada proceso
- ✅ Memoria total consumida por cada proceso
- ✅ Métricas en tiempo real
- ✅ Datos retenidos 30 días en CloudWatch Logs (ajustable)

---

### Por qué las otras opciones fallan

| Opción | Por qué no cumple el requisito |
|---|---|
| **CPU% y MEM% en consola RDS** | Esas métricas **no están disponibles** directamente en la consola RDS como lo describe la opción |
| **CloudWatch estándar** | Solo ve CPU agregada desde el hipervisor, no por proceso individual |
| **Script custom → CloudWatch** | No tienes acceso directo al OS de RDS (a diferencia de EC2). No puedes instalar agentes o scripts personalizados |

---

### El punto clave sobre RDS vs EC2

```
EC2                              RDS
───                              ───
✅ Acceso al OS                  ❌ Sin acceso directo al OS
✅ Puedes instalar agentes        ❌ No puedes instalar scripts
✅ Custom CloudWatch agent        ✅ Enhanced Monitoring (agente
                                    gestionado por AWS)
```

> En RDS, AWS gestiona el OS por ti. Por eso la única forma de obtener métricas a nivel de proceso es mediante **Enhanced Monitoring**, que usa un agente que AWS instala y administra automáticamente.

---

### Regla mental para el examen

> - Monitorear **procesos/threads individuales** en RDS → **Enhanced Monitoring**
> - Monitorear **métricas generales** de la instancia RDS → **CloudWatch**
> - Monitorear **queries lentas o rendimiento SQL** → **RDS Performance Insights**
 
 &nbsp;   
 
 &nbsp;   
 
 &nbsp;

## DynamoDB Streams + Lambda + SNS: Feature de Notificaciones

### El flujo de la solución correcta

```
Usuario actualiza su perfil
         ↓
   DynamoDB Table
         ↓
   DynamoDB Stream  ←── debe habilitarse manualmente
         ↓
  Lambda (trigger)  ←── necesita IAM role con permisos
         ↓
     SNS Topic
         ↓
  Suscriptores reciben email
```

---

### ¿Qué es DynamoDB Streams?

Es un flujo **ordenado cronológicamente** de todos los cambios en una tabla DynamoDB. Captura:
- Creaciones (INSERT)
- Actualizaciones (UPDATE)
- Eliminaciones (DELETE)

Cada cambio genera un **stream record** con la clave primaria del ítem modificado. Opcionalmente puedes capturar la imagen "antes" y "después" del cambio.

> ⚠️ **DynamoDB Streams NO está habilitado por defecto.** Debe activarse manualmente.

---

### Por qué las otras opciones fallan

| Opción | Error específico |
|---|---|
| **DAX + trigger + Lambda + SNS** | DAX es un **caché de lectura en memoria** (acelera reads), no captura cambios de datos. No sirve para este caso |
| **KCL + Kinesis Adapter + SNS** | Solución técnicamente válida, pero **omite habilitar DynamoDB Streams** primero |
| **Lambda + Kinesis Adapter + SNS** | Mismo problema: asume que el Stream ya está activo, pero no menciona habilitarlo |

Las dos últimas opciones son variantes del mismo error: **dar por sentado que Streams está habilitado**.

---

### DAX vs DynamoDB Streams: distinción clave

```
DAX (DynamoDB Accelerator)       DynamoDB Streams
──────────────────────────       ─────────────────
Caché en memoria                 Registro de cambios
Mejora latencia de LECTURA       Captura eventos de escritura
Responde consultas rápido        Alimenta triggers y pipelines
No detecta cambios               Ordenado cronológicamente
```

---

### Regla mental para el examen

> - Reaccionar a **cambios en DynamoDB** en tiempo real → **DynamoDB Streams + Lambda trigger**
> - **Notificar a múltiples suscriptores** → **SNS Topic**
> - **Acelerar lecturas** en DynamoDB → **DAX**
> - DynamoDB Streams **no se activa solo** → siempre debe habilitarse explícitamente
  
 &nbsp;   
 
 &nbsp;   
 
 &nbsp;

## Security Groups: Acceso SSH desde una IP específica

### La respuesta correcta y por qué

```
Inbound Rule:
├── Protocol: TCP      ← SSH usa TCP, no UDP
├── Port: 22           ← Puerto estándar de SSH
└── Source: 110.238.98.71/32  ← /32 = exactamente una IP
```

---

### Los 4 conceptos que evalúa esta pregunta

**1. Inbound vs Outbound**
```
Inbound  → tráfico que ENTRA a la instancia  ← necesario para SSH
Outbound → tráfico que SALE de la instancia
```
Alguien se conecta *hacia* tu instancia por SSH → regla **Inbound**.

**2. TCP vs UDP**
```
SSH  → TCP puerto 22  ✅
DNS  → UDP puerto 53
RDP  → TCP puerto 3389
```
SSH siempre usa **TCP**. Especificar UDP simplemente no funcionaría.

**3. Notación CIDR /32**
```
/32  → 1 IP exacta        (110.238.98.71/32)     ← aquí
/24  → 256 IPs            (110.238.98.0/24)
/16  → 65,536 IPs         (110.238.0.0/16)
/0   → Todas las IPs      (0.0.0.0/0)
```

**4. Security Groups son stateful**
> Como los Security Groups son **stateful**, el tráfico de retorno (respuesta SSH) se permite automáticamente, sin necesidad de una regla Outbound explícita.

---

### Por qué cada opción incorrecta falla

| Opción | Error |
|---|---|
| Inbound, **UDP**, port 22, /32 | SSH usa TCP, no UDP |
| **Outbound**, TCP, port 22, /32 | Dirección incorrecta; SSH entrante necesita regla Inbound |
| **Outbound**, UDP, port 22, 0.0.0.0/0 | Dos errores: Outbound + UDP + abre a todas las IPs |

---

### Regla mental para el examen

> SSH → siempre **Inbound + TCP + puerto 22 + /32** para una IP específica
  
 &nbsp;   
 
 &nbsp;   
 
 &nbsp;

## API Gateway: Throttling y Caché para Manejar Traffic Spikes

### El problema del escenario

Un pico masivo de tráfico puede **sobrecargar los sistemas backend** (Lambda, bases de datos, etc.). Se necesita protegerlos sin migrar a otra arquitectura.

---

### La solución: Throttling + Result Caching en API Gateway

Estas dos funciones actúan como **escudo protector** del backend:

```
Internet → API Gateway → Lambda → Backend
              ↑
    [Throttling + Cache]
    Filtra y absorbe el tráfico
    antes de que llegue al backend
```

**Throttling (límite de solicitudes):**
```
Rate limit  → máx. requests por segundo (ej: 1,000 req/s)
Burst limit → pico momentáneo permitido  (ej: 2,000 req/s por segundos)
Excede límite → respuesta HTTP 429 (Too Many Requests)
               → el SDK de API Gateway reintenta automáticamente
```

**Result Caching:**
```
Primera request  → va al backend → respuesta guardada en caché
Requests siguientes → API Gateway responde desde caché
                      sin tocar el backend
```

---

### Por qué las otras opciones no son correctas

| Opción | Por qué falla |
|---|---|
| **Migrar a EC2 + ELB + Auto Scaling** | Innecesario. Lambda + API Gateway ya es escalable por diseño |
| **CloudFront frente a API Gateway** | CloudFront mejora latencia de entrega de contenido estático, pero no protege el backend de requests excesivos |
| **Mover Lambda a una VPC** | Irrelevante para el problema. VPC controla networking/aislamiento, no manejo de tráfico |

---

### Throttling vs Caché: roles distintos pero complementarios

```
Throttling                       Result Caching
──────────                       ──────────────
Limita CUÁNTAS requests          Limita CUÁNTAS requests
pasan por segundo                llegan al backend
                                 
Protege contra floods            Protege contra requests
y ataques de volumen             repetidas e idénticas

Responde 429 al exceso           Responde desde memoria
```

---

### Regla mental para el examen

> - Proteger backend de **picos de tráfico** en API Gateway → **Throttling + Caching**
> - **Throttling** → controla la tasa de requests
> - **Caching** → evita llamadas repetidas al backend
> - **CloudFront** → latencia y distribución de contenido, no protección de backend
  
&nbsp;   

&nbsp;   

&nbsp;

## FSx for NetApp ONTAP: Block Storage Multi-AZ para Windows

### Los dos requisitos clave del escenario

| Requisito | Implicación |
|---|---|
| **Alta disponibilidad multi-AZ** | El storage debe sobrevivir la caída de una AZ |
| **Block storage de baja latencia** | Se necesita protocolo de bloque (iSCSI), no file storage genérico |

---

### ¿Por qué FSx for NetApp ONTAP es la respuesta?

Es el único servicio de AWS que combina los tres elementos necesarios simultáneamente:

```
FSx for NetApp ONTAP
├── ✅ Multi-AZ nativo → alta disponibilidad entre zonas
├── ✅ Protocolo iSCSI → block storage de baja latencia
├── ✅ Compatible con Windows Server (también SMB, NFS)
└── ✅ Latencia sub-millisegundo con almacenamiento SSD
```

---

### Comparación de todas las opciones

| Servicio | Protocolo | Multi-AZ | Block Storage | Windows | Veredicto |
|---|---|---|---|---|---|
| **FSx for Windows File Server** | SMB | ✅ | ❌ Solo file | ✅ | ❌ No soporta iSCSI/block |
| **Amazon EFS** | NFS | ✅ | ❌ Solo file | ❌ Optimizado Linux | ❌ No apto para Windows |
| **Amazon S3** | HTTP/REST | ✅ | ❌ Object storage | ⚠️ | ❌ No es block storage |
| **FSx for NetApp ONTAP** | iSCSI, SMB, NFS | ✅ | ✅ | ✅ | ✅ Cumple todo |

---

### Los tres tipos de almacenamiento y sus protocolos

```
Block Storage   → iSCSI, EBS          → baja latencia, apps críticas
File Storage    → SMB, NFS            → archivos compartidos
Object Storage  → HTTP/REST (S3)      → datos no estructurados, backups
```

> Una aplicación de trading financiero necesita **block storage** por su naturaleza transaccional y requerimiento de latencia mínima.

---

### Diferencia entre los dos FSx para Windows

```
FSx for Windows File Server      FSx for NetApp ONTAP
───────────────────────          ────────────────────
Solo protocolo SMB               SMB + NFS + iSCSI
Solo file storage                File + Block storage
Exclusivo para Windows           Multi-OS (Win, Linux, Mac)
Sin iSCSI                        ✅ iSCSI nativo
```

---

### Regla mental para el examen

> - **Block storage + Multi-AZ + Windows + iSCSI** → **FSx for NetApp ONTAP**
> - **File storage compartido solo para Windows** → **FSx for Windows File Server**
> - **File storage para Linux/multi-OS** → **EFS**
> - **Object storage escalable** → **S3**
   
&nbsp;   

&nbsp;   

&nbsp;

## Auto Scaling + Multi-AZ: Alta Disponibilidad y Fault Tolerance

### El razonamiento crítico de esta pregunta

El requisito dice "mínimo 2 instancias **siempre funcionando**". La trampa está en entender que **fault tolerance ≠ simplemente tener Multi-AZ**.

---

### El concepto de fault tolerance aplicado aquí

```
Sin fault tolerance (min=2, 1 por AZ):
├── Normal:  AZ-A(1) + AZ-B(1) = 2 ✅
└── AZ falla: AZ-A(0) + AZ-B(1) = 1 ❌ (ASG tarda en lanzar nueva instancia)

Con fault tolerance (min=4, 2 por AZ):
├── Normal:  AZ-A(2) + AZ-B(2) = 4 ✅
└── AZ falla: AZ-A(0) + AZ-B(2) = 2 ✅ (mínimo garantizado inmediatamente)
```

> La clave: ASG **no lanza instancias instantáneamente**. Si dependes del autoscaling para recuperar el mínimo tras un fallo, habrá un período con menos instancias de las requeridas.

---

### Análisis de todas las opciones

| Opción | Min | Max | Distribución | Problema |
|---|---|---|---|---|
| Min=2, Max=6, todo en AZ-A | 2 | 6 | Single AZ | ❌ Sin fault tolerance, AZ única |
| Min=2, Max=6, 1 por AZ | 2 | 6 | Multi-AZ | ❌ Si una AZ cae → queda 1 instancia temporalmente |
| Min=2, Max=4, 2 por AZ | 2 | 4 | Multi-AZ | ❌ Max incorrecto: en peak + fallo de AZ solo llega a 4, no 6 |
| **Min=4, Max=6, 2 por AZ** | **4** | **6** | **Multi-AZ** | ✅ Cumple todo |

---

### Por qué la respuesta correcta es Min=4, Max=6

```
Escenario normal (sin fallos):
AZ-A(2) + AZ-B(2) = 4 instancias corriendo ✅

Escenario de fallo de AZ:
AZ-A(0) + AZ-B(2) = 2 instancias → mínimo requerido garantizado ✅

Escenario de peak load:
AZ-A(3) + AZ-B(3) = 6 instancias → máximo requerido ✅

Escenario peak + fallo de AZ:
AZ-A(0) + AZ-B(6) = hasta 6 → performance mantenida ✅
```

---

### Regla mental para el examen

> Cuando el requisito sea **"mínimo N instancias incluso ante fallo de AZ"**:
> - Distribuye N instancias **por cada AZ**
> - El mínimo del ASG debe ser **N × número de AZs**
> - Así, si una AZ cae, las AZs restantes ya tienen el mínimo requerido **sin esperar autoscaling**
   
&nbsp;   

&nbsp;   

&nbsp;

## CloudFront Signed Cookies vs Signed URLs: Control de Acceso Privado

### La decisión clave del escenario

Dos requisitos determinan la solución:
1. Acceso a **múltiples archivos** privados
2. **Sin cambiar las URLs** actuales

---

### Signed URLs vs Signed Cookies: cuándo usar cada uno

```
Signed URLs                      Signed Cookies
───────────                      ──────────────
Acceso a UN archivo individual   Acceso a MÚLTIPLES archivos ✅
Cambia la URL del recurso        NO cambia las URLs actuales ✅
Útil para descargas únicas       Ideal para áreas de suscriptores
Soporta distribuciones RTMP      No soporta RTMP
Para clientes sin soporte        Para navegadores estándar
de cookies
```

> El escenario necesita **múltiples archivos + sin cambiar URLs** → **Signed Cookies** ✅

---

### ¿Cómo funcionan los Signed Cookies?

```
1. Usuario paga suscripción
         ↓
2. Aplicación verifica membresía
         ↓
3. App envía Set-Cookie headers al navegador
         ↓
4. Navegador incluye cookie en cada request a CloudFront
         ↓
5. CloudFront valida la cookie → permite acceso a contenido privado
         ↓
6. Las URLs del contenido NO cambian ✅
```

---

### Por qué las otras opciones fallan

| Opción | Por qué es incorrecta |
|---|---|
| **Match Viewer** | Es una *Origin Protocol Policy* que decide si CloudFront usa HTTP o HTTPS para hablar con el origen. No controla acceso de usuarios |
| **Signed URL** | Acceso a archivos individuales + **cambia las URLs** → viola el segundo requisito |
| **Field-Level Encryption** | Protege datos sensibles que los **usuarios suben** al servidor (upload). No controla acceso a descargas de contenido privado |

---

### Regla mental para el examen

| Situación | Solución |
|---|---|
| Acceso a **un archivo** específico | Signed URL |
| Acceso a **múltiples archivos** / área de suscriptores | Signed Cookies |
| **Sin cambiar URLs** actuales | Signed Cookies |
| Cliente **sin soporte de cookies** | Signed URL |
| Distribución **RTMP** | Signed URL (Signed Cookies no lo soporta) |
   
&nbsp;   

&nbsp;   

&nbsp;

## Egress-Only Internet Gateway + AWS Network Firewall: Seguridad IPv6

### Los tres requisitos del escenario

1. **Solo tráfico saliente** IPv6 hacia internet
2. **Bloquear conexiones entrantes** iniciadas desde internet
3. **Inspección y filtrado** de tráfico

---

### ¿Por qué Egress-Only Internet Gateway?

IPv6 tiene una característica importante que lo diferencia de IPv4:

```
IPv4                             IPv6
────                             ────
IPs privadas por defecto         IPs públicas por defecto
NAT Gateway para salir           Egress-Only IGW para salir
  a internet de forma segura       a internet de forma segura
```

Como las IPs IPv6 son públicas por defecto, necesitas un componente que permita **salir pero no entrar**:

```
Egress-Only Internet Gateway
├── ✅ Permite tráfico IPv6 SALIENTE (instancia → internet)
├── ✅ BLOQUEA conexiones IPv6 ENTRANTES (internet → instancia)
├── ✅ Altamente disponible y escalable
└── ✅ Exclusivo para IPv6
```

---

### La solución completa

```
Internet
   ↕ (solo salida)
Egress-Only IGW
   ↕
AWS Network Firewall  ← inspección + filtrado
   ↕
Private Subnet
   └── EC2 Instance
```

---

### Por qué las otras opciones fallan

| Opción | Componente de red | Problema | Componente de seguridad | Problema |
|---|---|---|---|---|
| Public subnet + **Internet Gateway** | IGW permite tráfico bidireccional | ❌ No bloquea inbound IPv6 | **Traffic Mirroring** | ❌ Solo copia tráfico para análisis, no filtra |
| Private subnet + **PrivateLink** | Conecta a servicios AWS, no a internet | ❌ No maneja IPv6 público | **GuardDuty** | ❌ Detecta amenazas, no inspecciona/filtra tráfico |
| Private subnet + **NAT Gateway** | NAT64 traduce IPv6→IPv4 | ❌ No bloquea inbound IPv6 | **Firewall Manager** | ❌ Gestiona políticas de firewall, no inspecciona tráfico |

---

### Distinción entre servicios de seguridad de red

```
AWS Network Firewall    → Inspección + filtrado activo de tráfico ✅
AWS Firewall Manager    → Gestión centralizada de políticas (no inspecciona)
Amazon GuardDuty        → Detección de amenazas con ML (no filtra tráfico)
Traffic Mirroring       → Copia tráfico para análisis externo (no filtra)
```

---

### Regla mental para el examen

> - **Solo salida IPv6** (bloquear inbound) → **Egress-Only Internet Gateway**
> - **Solo salida IPv4** (instancias privadas) → **NAT Gateway**
> - **Entrada y salida** → **Internet Gateway** (público)
> - **Inspección + filtrado de tráfico en VPC** → **AWS Network Firewall**
   
&nbsp;   

&nbsp;   

&nbsp;

## S3 Lifecycle Policies: Almacenamiento Cost-Effective para Archivos Antiguos

### Los requisitos del escenario

- Archivos **mayores de 2 años** → mover a storage más barato
- Solución **escalable, durable y de alta disponibilidad**
- **Costo-efectiva**

---

### Las dos respuestas correctas: S3 con Lifecycle Policies

S3 permite transicionar objetos automáticamente entre clases de almacenamiento:

```
S3 Standard (0-2 años)
         ↓  [Lifecycle Rule: después de 730 días]
         ├──→ S3 Standard-IA   (acceso infrecuente, aún rápido)
         └──→ S3 Glacier       (archivado, acceso en 1-5 min con Expedited)
```

Ambas opciones cumplen los requisitos porque S3 no tiene límite máximo en días para lifecycle rules.

---

### Por qué las otras opciones fallan

**❌ Amazon EFS + lifecycle policy hacia EFS-IA**
```
EFS Lifecycle máximo: 365 días (1 año)
Requisito:           730 días (2 años)
→ Técnicamente imposible de cumplir con EFS
```

**❌ Amazon EBS + Data Lifecycle Manager (DLM)**
```
EBS problemas:
├── Más costoso que S3
├── No es escalable para múltiples EC2 (limitaciones de acceso simultáneo)
├── Multi-attach solo en Provisioned IOPS → muy caro
└── DLM gestiona snapshots, no transiciones de storage class
```

**❌ RAID 0 con múltiples EBS + DLM**
```
RAID 0  → Mejora rendimiento I/O (striping)
RAID 1  → Redundancia (mirroring)
Ninguno → Soluciona el problema de costo/escalabilidad
Además: mismos problemas de costo que EBS estándar
```

---

### Comparación de clases S3 para este caso

| Clase | Acceso | Costo almacenamiento | Ideal para |
|---|---|---|---|
| S3 Standard | Inmediato | Alto | Archivos activos (0-2 años) |
| S3 Standard-IA | Inmediato | Medio | Acceso infrecuente pero rápido |
| S3 Glacier | 1-5 min (Expedited) | Bajo | Archivado largo plazo ✅ |
| S3 Glacier Deep Archive | Horas | Mínimo | Archivado raramente accedido |

---

### Regla mental para el examen

> - Mover objetos automáticamente según antigüedad → **S3 Lifecycle Policy**
> - EFS lifecycle: máximo **365 días** → no sirve para períodos mayores a 1 año
> - EBS → costoso, no escalable para múltiples instancias simultáneas
> - **S3 siempre gana** en escalabilidad, durabilidad y costo para almacenamiento de archivos
   
&nbsp;   

&nbsp;   

&nbsp;

## S3 Transfer Acceleration + Multipart Upload: Transferencia Global Rápida

### El contexto del escenario

```
Múltiples países          →          N. Virginia (us-east-1)
(500 GB por sitio)                   Weather App + S3 Bucket
     ↑
Conexión de alta velocidad disponible
→ El problema no es el ancho de banda local,
  sino la LATENCIA de larga distancia en internet
```

---

### La solución: Transfer Acceleration + Multipart Upload

Estas dos tecnologías se complementan perfectamente:

**Transfer Acceleration** resuelve el problema de distancia:
```
Sin Transfer Acceleration:
Usuario → Internet público (lento, ruta impredecible) → S3 N.Virginia

Con Transfer Acceleration:
Usuario → Edge Location CloudFront más cercana → Red privada AWS (rápida) → S3 N.Virginia
         (corto tramo internet)                  (backbone optimizado)
```
Mejora de velocidad: **50-500%** en transferencias de larga distancia.

**Multipart Upload** resuelve el problema del tamaño:
```
Archivo 500 GB dividido en partes
├── Parte 1 ──┐
├── Parte 2 ──┼──→ S3 (en paralelo) → ensamblado automático
├── Parte 3 ──┘
└── ...
Ventajas: transferencia paralela + recuperación ante fallos por parte
```

---

### Por qué las otras opciones son más lentas

| Opción | Tiempo aproximado | Por qué no es la más rápida |
|---|---|---|
| **Snowball Edge** | ~1 semana end-to-end | Es físico: envío, carga, ingestión en AWS |
| **S3 Cross-Region Replication** | ~15 minutos de replicación | Doble transferencia: subir + replicar. No es inmediato |
| **Site-to-Site VPN** | Variable, pero lento | Diseñado para conectar redes on-premises a VPC, no para transferencia masiva de datos |

---

### Regla mental para el examen

> - Transferencia **rápida** de datos a S3 desde **múltiples ubicaciones globales** → **Transfer Acceleration + Multipart Upload**
> - Transferencia de **datos masivos** (petabytes) sin internet disponible → **Snowball / Snowball Edge**
> - **Replicación automática** entre regiones S3 → **Cross-Region Replication** (no es la más rápida)
> - **Conectar red on-premises a VPC** → **Site-to-Site VPN / Direct Connect**
   
&nbsp;   

&nbsp;   

&nbsp;

## Aurora Global Database: Disaster Recovery Multi-Región

### Los dos métricas clave del escenario

```
RPO (Recovery Point Objective) = 1 segundo
→ Máxima pérdida de datos aceptable

RTO (Recovery Time Objective) < 1 minuto
→ Máximo tiempo para restaurar el servicio
```

Estas métricas son **extremadamente exigentes** y eliminan la mayoría de opciones.

---

### ¿Por qué Aurora Global Database es la respuesta?

```
Región primaria (us-east-1)
        ↓ replicación storage-based
        ↓ latencia < 1 segundo ← cumple RPO ✅
Región secundaria (eu-west-1)
        ↓ si hay fallo regional
        ↓ promoción a lectura/escritura < 1 minuto ← cumple RTO ✅
```

Características clave:
- Replicación a nivel de **storage** (no a nivel de base de datos)
- Sin impacto en performance de la región primaria
- Lecturas locales de baja latencia en cada región
- Failover **automático** entre regiones

---

### Por qué las otras opciones no cumplen RPO/RTO

| Opción | Tipo DB | RPO real | RTO real | Problema |
|---|---|---|---|---|
| **RDS PostgreSQL + cross-region replicas** | Relacional | **Minutos** | Minutos | Replication lag supera el RPO de 1 segundo |
| **DynamoDB Global Tables** | **NoSQL** | ~1 segundo | Minutos | No es base de datos relacional |
| **Amazon Timestream** | Time-series | N/A | N/A | Para IoT/analytics, no uso relacional general |
| **Aurora Global Database** | Relacional | **< 1 segundo** | **< 1 minuto** | ✅ Cumple ambos requisitos |

---

### RPO vs RTO: la distinción conceptual

```
Fallo ocurre aquí
        ↓
←──────────────── RPO ────────────────→
Último backup/sync              Momento del fallo
(cuántos datos perdemos)

        ↓ comienza recuperación
←──────────────── RTO ────────────────→
Inicio del fallo            Sistema restaurado
(cuánto tarda la recuperación)
```

---

### Regla mental para el examen

> - **RPO en segundos + RTO en minutos + relacional + multi-región** → **Aurora Global Database**
> - **Multi-región NoSQL** → DynamoDB Global Tables
> - **Disaster recovery relacional menos exigente** → RDS cross-region read replicas
> - **Datos de series de tiempo** (IoT, métricas) → Amazon Timestream
   
&nbsp;   

&nbsp;   

&nbsp;

## Cifrado de Secrets en EKS: etcd Key-Value Store

### El problema central

En Amazon EKS, los secrets de Kubernetes (contraseñas, API keys, etc.) se almacenan en **etcd**, un almacén distribuido clave-valor. Por defecto, **estos secrets NO están cifrados**, lo que representa un riesgo de seguridad.

---

### La solución: Secret Encryption con KMS en EKS

```
Sin cifrado (default):
Kubernetes Secret → etcd → texto plano ❌

Con KMS encryption habilitado:
Kubernetes Secret → KMS cifra → etcd → datos cifrados en reposo ✅
```

El proceso:
1. Crear una **KMS key** específica para el cluster EKS
2. Configurar el cluster para **cifrar secrets antes de guardarlos** en etcd
3. Todo el contenido sensible en etcd queda cifrado en reposo

---

### Por qué las otras opciones no resuelven el problema

| Opción | Qué hace realmente | Por qué no aplica |
|---|---|---|
| **AWS Secrets Manager + KMS** | Gestiona y recupera secrets externamente | No cifra datos **dentro de etcd**. Es para acceder a secrets, no para proteger el almacén interno de Kubernetes |
| **EBS Volume Encryption** | Cifra los volúmenes de los worker nodes | Los worker nodes ≠ etcd. EBS no almacena la configuración interna del cluster |
| **EBS CSI Driver** | Proporciona storage persistente para pods | Almacenamiento para aplicaciones, no para el etcd del control plane |

---

### La distinción clave: etcd vs otras capas de storage

```
EKS Cluster
├── Control Plane
│   └── etcd ← aquí viven los Kubernetes Secrets
│              ← ESTO necesita KMS encryption
│
└── Worker Nodes
    └── EBS Volumes ← storage de aplicaciones/pods
                      (EBS encryption es diferente)
```

---

### Secrets Manager vs KMS encryption en EKS

```
AWS Secrets Manager          KMS Secret Encryption en EKS
───────────────────          ────────────────────────────
Almacén externo de secrets   Cifra el almacén interno (etcd)
Apps recuperan secrets vía   Transparente para las apps
API de Secrets Manager       
Rotación automática          Control criptográfico directo
Útil para secrets de apps    Necesario para compliance de etcd
```

---

### Regla mental para el examen

> - Cifrar **secrets dentro de etcd en EKS** → **KMS secret encryption en el cluster EKS**
> - Gestionar secrets que las **apps consumen** → **AWS Secrets Manager**
> - Cifrar **discos de worker nodes** → **EBS encryption**
> - Storage **persistente para pods** → **EBS CSI Driver**
   
&nbsp;   

&nbsp;   

&nbsp;

## AWS Lake Formation: Data Lake Centralizado Multi-Cuenta

### ¿Qué es AWS Lake Formation?

Es un servicio que simplifica la creación de un **data lake seguro** en días, no meses. Actúa como capa de gobierno sobre Amazon S3.

```
Múltiples cuentas AWS
├── Cuenta A (datos ventas)
├── Cuenta B (datos clientes)     →    Lake Formation    →   Data Lake
└── Cuenta C (datos operaciones)       (cuenta central)      en S3
```

---

### Componentes clave de Lake Formation

```
Amazon S3          → Capa de almacenamiento del data lake
AWS Glue           → Data Catalog (describe datasets disponibles)
Lake Formation     → Gobierno, seguridad y control de acceso
IAM / AD           → Gestión de identidades y permisos
```

**Control de acceso granular:**
- Permisos sobre **tablas y columnas** (no sobre buckets/objetos como S3 nativo)
- Grant/revoke simple a usuarios IAM, roles, grupos, Active Directory
- Cross-account sharing **incluido y gratuito**

---

### Por qué las otras opciones fallan

| Opción | Problema |
|---|---|
| **Amazon Data Firehose** | Configurar Firehose en cada cuenta es costoso e impráctico. Lake Formation ofrece cross-account sharing gratis |
| **Lambda + EventBridge** | Técnicamente posible con SDK, pero muy difícil de gestionar. Viola el requisito de "minimizar overhead operacional" |
| **AWS Control Tower** | Gobierna y gestiona **múltiples cuentas AWS** en general, no está diseñado específicamente para consolidar datos en S3 |

---

### Regla mental para el examen

> - **Consolidar datos de múltiples cuentas** con mínimo overhead → **AWS Lake Formation**
> - **Catalogar y describir datasets** → **AWS Glue Data Catalog** (integrado en Lake Formation)
> - **Streaming de datos hacia S3/Redshift** → **Amazon Data Firehose**
> - **Gobernar múltiples cuentas AWS** (no solo datos) → **AWS Control Tower**
   
&nbsp;   

&nbsp;   

&nbsp;

## Migración Oracle a AWS: DMS + RDS Multi-AZ

### Los dos requisitos del escenario

1. **Migrar** la base de datos Oracle on-premises a AWS
2. **Alta disponibilidad** ante fallos de servidor de base de datos

---

### Las dos respuestas correctas

**1. AWS Database Migration Service (DMS) → para la migración**
```
On-premises Oracle  →  AWS DMS  →  RDS Oracle
                       ↑
               - Mínimo downtime
               - Zero data loss
               - Soporta +20 motores
               - Oracle → RDS Oracle (migración homogénea)
```

**2. RDS Oracle con Multi-AZ → para alta disponibilidad**
```
AZ-A: RDS Oracle (primario)  ←→  AZ-B: RDS Oracle (standby)
         ↓ sincronización síncrona
Si primario falla → failover automático al standby
Mismo endpoint → aplicación no necesita cambios
```

---

### Por qué las otras opciones fallan

| Opción | Por qué es incorrecta |
|---|---|
| **RDS Oracle con RMAN** | Oracle Recovery Manager **no está soportado** en RDS. AWS gestiona los backups por ti |
| **AWS Schema Conversion Tool** | SCT es para migraciones **heterogéneas** (Oracle → PostgreSQL). Este caso es Oracle → Oracle (homogénea), no necesita conversión de esquema |
| **Aurora single instance** | Sin Multi-AZ = sin alta disponibilidad. No apto para cargas críticas de producción |

---

### Migración homogénea vs heterogénea

```
Homogénea (mismo motor)          Heterogénea (diferente motor)
────────────────────             ─────────────────────────────
Oracle → Oracle ✅ aquí          Oracle → PostgreSQL
MySQL → MySQL                    SQL Server → Aurora
Solo necesita DMS                Necesita SCT + DMS
```

> **Regla:** Si el motor de origen y destino son **iguales** → solo DMS. Si son **diferentes** → SCT primero para convertir el esquema, luego DMS para migrar los datos.

---

### Regla mental para el examen

> - **Migrar base de datos** a AWS con mínimo downtime → **AWS DMS**
> - **Cambiar de motor** de base de datos → **AWS SCT + DMS**
> - **Alta disponibilidad** en RDS ante fallos → **Multi-AZ**
> - **Escalar lecturas** en RDS → **Read Replicas**
> - Oracle RMAN en RDS → **no soportado**
   
&nbsp;   

&nbsp;   

&nbsp;

## NAT Gateway Multi-AZ: Eliminando el Single Point of Failure

### El problema del diseño actual

```
AZ-A (privada)  ──┐
                  ├──→ NAT Gateway único (en AZ-A) → Internet
AZ-B (privada)  ──┘
         ↑
Si AZ-A falla → NAT Gateway cae → AZ-B pierde acceso a internet ❌
```

---

### La solución correcta

Un NAT Gateway **por cada AZ**, con rutas en las **subnets privadas**:

```
AZ-A                              AZ-B
├── Private Subnet                ├── Private Subnet
│   └── route → NAT-GW-A          │   └── route → NAT-GW-B
└── Public Subnet                 └── Public Subnet
    └── NAT Gateway A                 └── NAT Gateway B
              ↓                                 ↓
                      Internet
```

Si AZ-A falla → instancias en AZ-B siguen usando su propio NAT-GW-B ✅

---

### Los dos detalles técnicos que determinan la respuesta correcta

**1. ¿Dónde vive el NAT Gateway?**
```
NAT Gateway → debe estar en subnet PÚBLICA
(necesita acceso directo a Internet Gateway)
```

**2. ¿Dónde se configura la route table?**
```
Route table → debe configurarse en subnet PRIVADA
(las instancias privadas son las que necesitan la ruta hacia el NAT GW)
```

---

### Por qué las otras opciones fallan

| Opción | Error específico |
|---|---|
| 1 NAT-GW por AZ + route en **subnet pública** | ❌ La route table debe ir en la **subnet privada**, no pública |
| **2** NAT-GW por AZ + route en subnet pública | ❌ Doble error: múltiples NAT-GW innecesarios + route en subnet incorrecta |
| **3** NAT-GW por AZ + route en subnet privada | ❌ 3 NAT Gateways por AZ es excesivo y costoso sin justificación. No alinea con cost-effectiveness |

---

### Regla mental para el examen

> - **Eliminar SPOF en NAT Gateway** → **1 NAT-GW por AZ en subnet pública**
> - **Route table** para instancias privadas → configurar en **subnet privada**
> - Cada AZ debe ser **independiente**: sus instancias privadas usan el NAT-GW de **su propia AZ**
> - Más de 1 NAT-GW por AZ → innecesario y costoso salvo requerimiento explícito

&nbsp;   

&nbsp;   

&nbsp;

## EBS + S3 + S3 Glacier: Solución de Almacenamiento en Tres Capas

### Los tres requisitos del escenario

```
1. Block storage persistente    → misión crítica
2. Object storage para backups  → primeros 30 días
3. Archival storage             → después de 30 días, largo plazo
```

---

### La solución correcta capa por capa

```
EC2 Instance
└── EBS Volume          ← bloque persistente para workloads críticos
         ↓ backup
    S3 Standard         ← object storage (días 0-30)
         ↓ lifecycle policy (día 30)
    S3 Glacier Flexible Retrieval  ← archivado largo plazo
```

---

### Las dos decisiones clave que determinan la respuesta

**1. EBS vs Instance Store**

| | EBS | Instance Store |
|---|---|---|
| Persistencia | ✅ Persiste independiente del EC2 | ❌ Temporal, se pierde al detener/terminar |
| Misión crítica | ✅ Ideal | ❌ No apto |
| Adjuntar después del lanzamiento | ✅ Sí | ❌ Solo al lanzar la instancia |
| Snapshots | ✅ Sí | ❌ No |

**2. S3 Glacier Flexible Retrieval vs S3 One Zone-IA**

| | S3 Glacier Flexible Retrieval | S3 One Zone-IA |
|---|---|---|
| Propósito | **Archivado** largo plazo | Acceso infrecuente (no archivado) |
| Costo | Muy bajo | Medio |
| Disponibilidad | Multi-AZ | **Una sola AZ** |
| Recuperación | Minutos a horas | Inmediata |

---

### El distractor del EBS Snapshot

> El enunciado menciona una "EBS snapshot retention rule" intencionalmente para confundir. Los EBS snapshots se almacenan internamente en S3, pero son gestionados por separado y **no pueden transicionarse** con lifecycle policies de S3 hacia Glacier.

---

### Regla mental para el examen

> - **Block storage persistente** para workloads críticos → **EBS**
> - **Block storage temporal** (alta I/O, efímero) → **Instance Store**
> - **Archivado** a largo plazo en S3 → **S3 Glacier Flexible Retrieval**
> - **Acceso infrecuente** pero no archivado → **S3 Standard-IA**
> - **One Zone-IA** → más barato pero sin redundancia multi-AZ, no apto para archivado crítico
   
&nbsp;   

&nbsp;   

&nbsp;

## API Gateway: Canary Release vs Otras Estrategias de Deployment

### Los requisitos del escenario

- **Mínima disrupción** para los clientes
- **Mínima pérdida de datos** durante la actualización
- Solución **costo-efectiva**

---

### ¿Qué es Canary Release?

Estrategia que libera la nueva versión a un **subconjunto pequeño** de usuarios primero:

```
Todo el tráfico (100%)
         ↓
   API Gateway
   ├── Producción (90%) → versión actual estable
   └── Canary Stage (10%) → nueva versión
              ↓
   Monitorear → si todo bien → aumentar % gradualmente
              → si hay problemas → rollback sin afectar al resto
              ↓
   Eventualmente: Canary promovido a Producción (100%)
```

---

### Comparación de las cuatro estrategias

| Estrategia | Aislamiento | Costo | Riesgo | Veredicto |
|---|---|---|---|---|
| **Canary Release** | Alto (% controlado) | Bajo (mismo GW) | Bajo | ✅ |
| **Blue-Green** | Alto (dos entornos) | **Alto** (doble infraestructura) | Bajo | ❌ Costoso |
| **Import-to-update (overwrite/merge)** | Ninguno | Bajo | **Alto** (afecta todo simultáneamente) | ❌ Riesgoso |
| **Nuevo API Gateway + mismo dominio** | Ninguno | Medio | **Alto** (DNS propagation delays + downtime) | ❌ Downtime |

---

### Canary vs Blue-Green: la distinción clave

```
Blue-Green                       Canary Release
──────────                       ──────────────
Dos entornos completos           Un entorno con % de tráfico dividido
Blue (actual) + Green (nuevo)    Producción + Canary stage
Switch total cuando validado     Incremento gradual del %
Mayor costo (doble infra)        Menor costo (mismo API Gateway)
Rollback: cambiar el switch      Rollback: reducir % a 0
```

> El escenario pide **costo-efectivo** → Blue-Green queda eliminado por su doble infraestructura.

---

### Regla mental para el examen

> - **Mínima disrupción + costo-efectivo** en API Gateway → **Canary Release**
> - **Dos entornos paralelos completos** → **Blue-Green** (más costoso pero más aislado)
> - Cuando el requisito menciona **"cost-effective"** y hay una opción Blue-Green → generalmente **no es la respuesta correcta**
   
&nbsp;   

&nbsp;   

&nbsp;

## Kinesis + Lambda + DynamoDB: Anonimización de PII en Tiempo Real

### El requisito crítico del escenario

> PII debe ser anonimizada **ANTES** de llegar a cualquier sistema de almacenamiento.

Esta condición elimina inmediatamente cualquier solución que almacene datos primero y anonimice después.

---

### La solución correcta: anonimización en tránsito

```
Fuentes múltiples
      ↓
Kinesis Data Stream    ← ingesta en tiempo real, escalable
      ↓
AWS Lambda             ← anonimiza PII EN TRÁNSITO (nunca toca storage)
      ↓
Amazon DynamoDB        ← solo recibe datos ya anonimizados ✅
      (NoSQL)
```

---

### Por qué las otras opciones violan el requisito principal

| Opción | El problema |
|---|---|
| **S3 → Lambda → DynamoDB** | PII se almacena en S3 **primero**, luego se anonimiza. Viola el requisito |
| **DynamoDB → DynamoDB Streams → Lambda** | PII se escribe en DynamoDB **primero**, luego Lambda anonimiza. Viola el requisito. Además, `AmazonDynamoDBFullAccess` viola el principio de **mínimo privilegio** |
| **Firehose → Redshift** | Redshift es un **data warehouse relacional**, no una base de datos NoSQL |

---

### La regla de oro: ¿cuándo ocurre la anonimización?

```
❌ Almacenar → Anonimizar    (S3 o DynamoDB primero)
              PII toca el storage aunque sea brevemente

✅ Anonimizar → Almacenar    (Lambda en tránsito)
              PII nunca llega al storage
```

---

### Comparación de servicios de streaming

| Servicio | Caso de uso | Procesa con Lambda |
|---|---|---|
| **Kinesis Data Streams** | Streaming en tiempo real, procesamiento personalizado | ✅ Sí |
| **Amazon Data Firehose** | Entrega directa a destinos (S3, Redshift, etc.) | ✅ Sí (transformación limitada) |
| **DynamoDB Streams** | Reaccionar a cambios en una tabla DynamoDB | ✅ Sí, pero datos ya en DB |

---

### Regla mental para el examen

> - **Streaming en tiempo real + transformación antes de almacenar** → **Kinesis Data Streams + Lambda**
> - **PII que no debe tocar ningún storage** → la transformación debe ocurrir **en tránsito**
> - **NoSQL en AWS** → **DynamoDB**
> - **Data warehouse relacional** → **Redshift** (no es NoSQL)
> - Permisos excesivos como `FullAccess` → siempre violación del **principio de mínimo privilegio**

&nbsp;   

&nbsp;   

&nbsp;

## AWS Shield Advanced: Protección contra DDoS

### Los niveles de protección DDoS en AWS

```
AWS Shield Standard (gratuito, automático)
├── Protección básica contra ataques comunes
├── Capa de red y transporte (L3/L4)
└── Incluido automáticamente para todos los clientes

AWS Shield Advanced (de pago, suscripción)
├── Todo lo de Standard +
├── Detección y mitigación de ataques sofisticados y grandes
├── Visibilidad en tiempo real de los ataques
├── Integración con AWS WAF
├── Acceso 24/7 al DDoS Response Team (DRT)
└── Protección contra cargos extra por spikes de DDoS en EC2/ELB/CloudFront/Route 53
```

---

### Por qué las otras opciones son insuficientes

| Opción | Propósito real | ¿Protege contra DDoS? |
|---|---|---|
| **AWS Firewall Manager** | Administración centralizada de WAF en múltiples cuentas | ❌ No mitiga DDoS directamente |
| **AWS WAF** | Filtra tráfico HTTP (SQL injection, XSS, patrones maliciosos) | ⚠️ Parcial, no suficiente para DDoS volumétrico |
| **Security Groups + NACLs** | Control de acceso a nivel de instancia/subnet | ⚠️ Útil pero insuficiente ante ataques masivos |
| **AWS Shield Advanced** | Detección y mitigación específica de DDoS | ✅ Solución diseñada exactamente para esto |

---

### Los servicios protegidos por Shield Advanced

```
AWS Shield Advanced protege:
├── Amazon EC2
├── Elastic Load Balancing (ELB)
├── Amazon CloudFront
└── Amazon Route 53
```

---

### Regla mental para el examen

> - **DDoS** → **AWS Shield** (Standard gratuito, Advanced para ataques sofisticados)
> - **SQL injection, XSS, tráfico HTTP malicioso** → **AWS WAF**
> - **Gestión centralizada de WAF en múltiples cuentas** → **AWS Firewall Manager**
> - **Inspección y filtrado de tráfico en VPC** → **AWS Network Firewall**
> - **Control de acceso a instancias/subnets** → **Security Groups + NACLs**
   
&nbsp;   

&nbsp;   

&nbsp;

## Auto Scaling: Target Tracking vs Otras Políticas de Escalado

### El problema del escenario

**Over-provisioning** = demasiados recursos activos → costos innecesariamente altos. Se necesita una política que ajuste la capacidad **dinámicamente y con precisión**.

---

### Comparación de todas las políticas de Auto Scaling

| Política | Cómo funciona | Ideal para | Problema |
|---|---|---|---|
| **Target Tracking** | Mantiene una métrica en un valor objetivo automáticamente | Optimización continua de costos ✅ | — |
| **Simple Scaling** | Escala cuando una alarma CloudWatch se dispara | Casos básicos | Debe esperar el **cooldown period** antes de escalar de nuevo |
| **Step Scaling** | Escala en pasos según el tamaño del breach de la alarma | Respuesta granular a cambios | Más complejo de configurar |
| **Scheduled Scaling** | Escala en horarios predefinidos | Tráfico **predecible** (ej: más usuarios de 9am-5pm) | No sirve para tráfico variable |
| **Suspend/Resume** | Pausa temporalmente todas las actividades de scaling | Mantenimiento temporal | No es una política de escalado dinámico |

---

### ¿Por qué Target Tracking es la mejor opción?

```
Ejemplo: Target = 50% CPU

CPU sube a 80% → ASG agrega instancias automáticamente
CPU baja a 30% → ASG remueve instancias automáticamente
                  ↑
         Sin esperar cooldown period
         Sin configurar alarmas manualmente
         Se ajusta a patrones cambiantes de carga
```

Ventajas clave:
- ✅ **No necesitas crear alarmas CloudWatch** manualmente
- ✅ **No hay cooldown period** que bloquee nuevas acciones
- ✅ Ajuste continuo → evita over-provisioning y under-provisioning
- ✅ Responde a cambios en patrones de carga dinámicamente

---

### Regla mental para el examen

> - **Optimizar costos + evitar over-provisioning** → **Target Tracking Scaling**
> - **Tráfico predecible** (horarios fijos) → **Scheduled Scaling**
> - **Respuesta escalonada** según magnitud del problema → **Step Scaling**
> - **Pausar scaling temporalmente** → **Suspend and Resume**
> - Simple Scaling → obsoleto en la práctica, tiene limitación del cooldown period
   
&nbsp;   

&nbsp;   

&nbsp;
   
## Migración .NET + Oracle a AWS: Mínimos Cambios, Alta Disponibilidad

### Los requisitos del escenario

- **Minimizar cambios** de desarrollo (no refactorizar)
- **Alta disponibilidad** en la nube
- **Más fácil de gestionar** que on-premises

---

### Las dos respuestas correctas

**1. Elastic Beanstalk Multi-AZ → para la aplicación .NET**
```
On-premises .NET (Windows Server + IIS)
         ↓ rehost (lift & shift)
Elastic Beanstalk Multi-AZ
├── Soporta .NET nativamente ✅
├── Gestiona automáticamente: EC2, Load Balancing, Scaling, Health monitoring
├── Sin cambios de código ✅
└── Multi-AZ = alta disponibilidad ✅
```

**2. RDS for Oracle Multi-AZ + DMS → para la base de datos**
```
On-premises Oracle Standard Edition
         ↓ migración homogénea (Oracle → Oracle)
RDS for Oracle Multi-AZ
├── Mismo motor = sin conversión de schema ✅
├── AWS DMS maneja la migración con mínimo downtime ✅
└── Multi-AZ = failover automático ✅
```

---

### Por qué las otras opciones violan los requisitos

| Opción | Tipo de migración | Problema |
|---|---|---|
| **Refactorizar a .NET Core + EKS/Fargate** | Refactor | Cambios significativos de código ❌ |
| **ECS + EC2 worker nodes + ECS Anywhere** | Replatform | Debes gestionar los EC2 subyacentes + cambios de plataforma ❌ |
| **AWS MGN para Oracle → EC2** | Rehost de DB en EC2 | MGN no es la herramienta adecuada para Oracle; además EC2 requiere más gestión que RDS ❌ |

---

### Los 6 tipos de migración ("6 Rs") aplicados aquí

```
Retire     → eliminar
Retain     → mantener on-premises
Rehost     → lift & shift sin cambios      ← Elastic Beanstalk aquí ✅
Replatform → lift & reshape (mínimos cambios de plataforma)
Repurchase → cambiar a SaaS
Refactor   → rediseñar la arquitectura     ← EKS/Fargate aquí ❌ (demasiados cambios)
```

---

### Regla mental para el examen

> - **"Minimizar cambios" + aplicación .NET** → **Elastic Beanstalk** (gestión automática, soporta .NET/IIS)
> - **Migración Oracle → Oracle** (homogénea) → **AWS DMS** (sin Schema Conversion Tool)
> - **Migración Oracle → otro motor** (heterogénea) → **AWS SCT + DMS**
> - **Rehost de servidores completos** (cualquier OS) → **AWS Application Migration Service (MGN)**
> - **Refactorizar = cambios de código** → contradice "minimizar cambios de desarrollo"

&nbsp;   

&nbsp;   

&nbsp;

## S3 Pre-Signed URLs: Control de Acceso a Contenido Privado

### El problema

Las fotos en S3 son **públicamente accesibles**, permitiendo que otros sitios las enlacen directamente (*hotlinking*). Esto consume el ancho de banda del propietario sin beneficio económico.

---

### La solución: Pre-Signed URLs con expiración

```
Antes (problemático):
Bucket S3 público → cualquiera enlaza las fotos directamente ❌

Después (solución):
Bucket S3 privado → nadie accede directamente
      ↓
Aplicación genera Pre-Signed URL con expiración
      ↓
URL válida solo por tiempo limitado (ej: 1 hora)
      ↓
Solo el usuario autorizado puede acceder ✅
```

**Cómo funciona una Pre-Signed URL:**
```
Requiere al generarla:
├── Credenciales de seguridad del propietario
├── Nombre del bucket
├── Object key
├── Método HTTP (GET para descarga)
└── Fecha/hora de expiración
```

---

### Por qué las otras opciones no son efectivas

| Opción | Por qué falla |
|---|---|
| **Bloquear IPs con NACL** | Los sitios ofensores pueden cambiar su IP fácilmente, eludiendo el bloqueo |
| **CloudFront** | Es una CDN que acelera la entrega de contenido, no restringe quién puede acceder |
| **Amazon WorkDocs** | Herramienta de colaboración de documentos, no diseñada para servir contenido estático web |

---

### Pre-Signed URLs vs Signed Cookies (recordando tema anterior)

```
Pre-Signed URLs (S3)             Signed Cookies (CloudFront)
────────────────────             ───────────────────────────
Control de acceso en S3          Control de acceso en CloudFront
Por objeto individual            Múltiples archivos a la vez
Sin cambiar URLs base            Sin cambiar URLs actuales
Tiempo de expiración configurable Tiempo de expiración configurable
```

---

### Regla mental para el examen

> - **Hotlinking / uso no autorizado** de objetos S3 → **quitar acceso público + Pre-Signed URLs**
> - **Pre-Signed URL** → acceso temporal y controlado a objetos S3 privados
> - **Bloquear IPs** → ineficiente, fácilmente eludible
> - **CloudFront** → velocidad de entrega, no control de acceso por sí solo
   
&nbsp;   

&nbsp;   

&nbsp;

## Lambda@Edge + Origin Failover: Performance y Resiliencia en CloudFront

### Los dos problemas del escenario

```
Problema 1: Login lento para usuarios globales
→ La autenticación viaja hasta el origen (servidor central)
→ Alta latencia para usuarios lejanos

Problema 2: Errores HTTP 504 (Gateway Timeout)
→ El origen falla ocasionalmente
→ No hay mecanismo de recuperación automática
```

---

### Las dos soluciones correctas

**1. Lambda@Edge → resuelve el login lento**
```
Sin Lambda@Edge:
Usuario (Tokio) → CloudFront Edge → Origen (us-east-1) → autenticación
                                    ←────── latencia alta ──────────

Con Lambda@Edge:
Usuario (Tokio) → CloudFront Edge (Tokio) → Lambda autentica aquí ✅
                  ↑ función ejecuta en la ubicación más cercana al usuario
```

Lambda@Edge se ejecuta en 4 puntos del ciclo CloudFront:
```
Viewer Request  → antes de que CloudFront procese la solicitud
Origin Request  → antes de enviar al origen
Origin Response → después de recibir respuesta del origen
Viewer Response → antes de enviar respuesta al usuario
```

**2. Origin Failover → resuelve los errores 504**
```
Grupo de orígenes:
├── Origen primario  → recibe tráfico normal
└── Origen secundario → CloudFront cambia automáticamente
                        si el primario devuelve errores HTTP específicos
                        (500, 502, 503, 504, etc.)
```

---

### Por qué las otras opciones no cumplen los requisitos

| Opción | Por qué falla |
|---|---|
| **Cache-Control max-age** | Mejora el cache de objetos estáticos, pero el problema es la **autenticación**, no el caching |
| **Multi-región + Route 53 latency routing** | Válido técnicamente, pero **muy costoso** (deployar en múltiples regiones). El escenario pide solución cost-effective |
| **Múltiples VPCs + Transit VPC + Lambda por región** | Complejidad y costos de setup/mantenimiento elevados vs Lambda@Edge que es serverless y automático |

---

### Regla mental para el examen

> - **Lógica de autenticación/personalización cerca del usuario** → **Lambda@Edge**
> - **Recuperación automática ante fallos del origen** → **CloudFront Origin Failover**
> - **Mejorar cache de contenido estático** → **Cache-Control / TTL**
> - **Enrutar por latencia entre regiones** → **Route 53 latency routing** (pero más costoso que Lambda@Edge)

&nbsp;   

&nbsp;   

&nbsp;

## Análisis de IAM Policy: Lectura de Permisos JSON

### Desglose de la política

```json
Statement 1:
{
  "Effect": "Allow",
  "Action": ["s3:Get*", "s3:List*"],
  "Resource": "*"          ← TODOS los buckets
}

Statement 2:
{
  "Effect": "Allow",
  "Action": "s3:PutObject",
  "Resource": "arn:aws:s3:::boracay/*"  ← SOLO bucket boracay
}
```

---

### Mapa completo de permisos

| Acción | ¿En qué recursos? | ¿Permitido? |
|---|---|---|
| `s3:Get*` (leer objetos) | **Todos** los buckets | ✅ |
| `s3:List*` (listar objetos) | **Todos** los buckets | ✅ |
| `s3:PutObject` (escribir) | Solo bucket **boracay** | ✅ |
| `s3:DeleteObject` (eliminar) | Ninguno | ❌ No está en la policy |
| `s3:PutBucketAcl` (cambiar permisos) | Ninguno | ❌ No está en la policy |

---

### Las tres respuestas correctas explicadas

**✅ Leer objetos de TODOS los buckets**
> `s3:Get*` con `Resource: "*"` → aplica a cualquier bucket de la cuenta

**✅ Escribir objetos en el bucket `boracay`**
> `s3:PutObject` con `Resource: "arn:aws:s3:::boracay/*"` → solo en boracay

**✅ Leer objetos del bucket `boracay`**
> Incluido en el primer statement (`s3:Get*` aplica a todos, incluyendo boracay)

---

### Por qué las otras opciones son incorrectas

**❌ "Puede cambiar permisos del bucket boracay"**
> Cambiar permisos requeriría `s3:PutBucketPolicy` o `s3:PutBucketAcl`. Ninguno está en la policy.

**❌ "Puede leer pero NO listar objetos en boracay"**
> Falso. `s3:List*` en `Resource: "*"` permite listar **todos** los buckets, incluyendo boracay.

**❌ "Puede leer Y eliminar objetos de boracay"**
> Puede leer ✅, pero eliminar requeriría `s3:DeleteObject`, que **no aparece** en ningún statement.

---

### Regla mental para el examen

> Al analizar una IAM policy, verifica siempre:
> 1. ¿Qué **acciones** están permitidas? (`Action`)
> 2. ¿En qué **recursos** aplican? (`Resource: "*"` vs ARN específico)
> 3. ¿El efecto es **Allow o Deny**?
> 4. Si una acción **no aparece** en la policy → está **denegada por defecto**
   
&nbsp;   

&nbsp;   

&nbsp;

## Redis AUTH en ElastiCache: Autenticación con Contraseña

### Los requisitos del escenario

- Autenticación con **contraseña** antes de ejecutar comandos Redis
- Soporte para comandos específicos como `MULTI EXEC`
- **Credenciales de larga duración** (long-lived credentials)
- Seguridad robusta

---

### La solución: Redis AUTH + Transit Encryption

```
Cliente → --transit-encryption-enabled → Canal cifrado (TLS)
                                              ↓
                                    --auth-token (contraseña)
                                              ↓
                                    Redis valida contraseña
                                              ↓
                                    Acceso permitido a comandos
                                    (incluyendo MULTI EXEC) ✅
```

Los dos parámetros son **complementarios y necesarios juntos**:

| Parámetro | Función |
|---|---|
| `--transit-encryption-enabled` | Cifra la comunicación cliente-Redis (TLS) |
| `--auth-token` | Requiere contraseña para ejecutar comandos |

> ⚠️ Redis AUTH **requiere** que el transit encryption esté habilitado. No puede usarse sin TLS.

---

### Por qué las otras opciones fallan

| Opción | Por qué es incorrecta |
|---|---|
| **AtRestEncryptionEnabled** | Cifra datos **en reposo** dentro del almacén en memoria. No protege la autenticación ni el acceso a comandos |
| **Solo transit encryption** | Cifra el canal pero **no requiere contraseña**. Falta el `--auth-token` |
| **IAM authentication token** | IAM no soporta comandos Redis como `MULTI EXEC`. Además, los tokens IAM **expiran cada 12 horas** → no son long-lived credentials ❌ |

---

### Comparación de cifrado en ElastiCache Redis

```
At-Rest Encryption          In-Transit Encryption        Redis AUTH
──────────────────          ─────────────────────        ──────────
Protege datos en disco      Protege datos en tránsito    Requiere contraseña
y en memoria                (canal TLS)                  para ejecutar comandos
AtRestEncryptionEnabled     transit-encryption-enabled   --auth-token
No requiere autenticación   No requiere autenticación    Long-lived credentials ✅
```

---

### Regla mental para el examen

> - **Autenticación con contraseña en Redis** → **Redis AUTH** (`--auth-token`)
> - Redis AUTH **siempre** requiere `--transit-encryption-enabled`
> - **Cifrado de datos en reposo** en ElastiCache → `AtRestEncryptionEnabled`
> - **IAM tokens** → expiran en 12h, no sirven para credenciales de larga duración en Redis
> - `MULTI EXEC` = transacción Redis → requiere Redis AUTH, no IAM
   
&nbsp;   

&nbsp;   

&nbsp;

## DynamoDB: Base de Datos NoSQL para Esquemas Flexibles

### Los requisitos clave del escenario

```
1. Escala global
2. Cambios frecuentes de schema → sin downtime ni degradación
3. Baja latencia en consultas de alto tráfico
```

---

### La decisión central: Relacional vs NoSQL

```
Relacional (RDS, Aurora)         NoSQL (DynamoDB)
────────────────────             ────────────────
Schema RÍGIDO                    Schema FLEXIBLE ✅
Cambios de schema = ALTER TABLE  Agrega/quita atributos libremente
Afecta toda la tabla             Cambios por ítem individual
Joins entre múltiples tablas     Datos jerárquicos en un solo ítem
Escala vertical (limitada)       Escala horizontal (global) ✅
ACID compliant (overhead)        Latencia baja en alto tráfico ✅
```

---

### ¿Por qué DynamoDB cumple cada requisito?

**Cambios frecuentes de schema sin downtime:**
```
Relacional:
ALTER TABLE usuarios ADD columna_nueva VARCHAR(100);
→ Bloquea la tabla durante la operación ❌
→ Afecta toda la tabla simultáneamente ❌

DynamoDB:
Ítem 1: {id, nombre, email}
Ítem 2: {id, nombre, email, telefono}  ← atributo nuevo, sin alterar otros
Ítem 3: {id, nombre, direccion}        ← estructura diferente, sin problema
→ Zero downtime ✅
```

**Escalabilidad global:**
- DynamoDB Global Tables → replicación multi-región automática
- Sin límite práctico de escala horizontal

**Baja latencia en alto tráfico:**
- Diseñado para respuestas en milisegundos a cualquier escala
- Las queries más comunes se optimizan en el diseño del schema

---

### Por qué las otras opciones fallan

| Opción | Por qué no aplica |
|---|---|
| **Aurora + Read Replicas** | Relacional → schema rígido, cambios requieren downtime |
| **RDS Multi-AZ** | Relacional → mismo problema de schema rígido |
| **Redshift** | OLAP (análisis de datos/reportes), no para aplicaciones transaccionales de alto tráfico |

---

### Regla mental para el examen

> - **Schema flexible + cambios frecuentes + alto tráfico** → **DynamoDB**
> - **Consultas complejas + relaciones entre tablas** → **RDS / Aurora**
> - **Análisis de grandes volúmenes de datos / OLAP** → **Redshift**
> - **Schema rígido** = relacional → `ALTER TABLE` causa downtime
   
&nbsp;   

&nbsp;   

&nbsp;

## DynamoDB: Diseño de Partition Keys para Alto Rendimiento

### El concepto central: ¿Cómo distribuye DynamoDB los datos?

```
Partition Key → determina en qué partición física se almacena el ítem
                     ↓
Cada partición tiene una porción del throughput provisionado
                     ↓
Si muchos requests van a la misma partición → "Hot Partition" ❌
Si requests se distribuyen uniformemente → throughput eficiente ✅
```

---

### Alta vs Baja cardinalidad

```
Baja cardinalidad (pocos valores distintos)
Ejemplo: partition key = "status" (valores: "active", "inactive")
├── Partición "active"   → recibe 95% del tráfico → HOT PARTITION ❌
└── Partición "inactive" → recibe 5% del tráfico  → subutilizada ❌

Alta cardinalidad (muchos valores distintos)
Ejemplo: partition key = "user_id" (millones de IDs únicos)
├── Partición user_001 → tráfico distribuido ✅
├── Partición user_002 → tráfico distribuido ✅
├── Partición user_003 → tráfico distribuido ✅
└── ... millones de particiones balanceadas ✅
```

---

### Por qué las otras opciones son incorrectas

| Opción | Por qué falla |
|---|---|
| **Baja cardinalidad** | Menos valores distintos = menos particiones = más concentración de tráfico = hot partitions |
| **Reducir número de partition keys** | Menos keys = menos distribución = peor rendimiento |
| **Evitar composite primary key** | Al contrario, una composite key (partition + sort key) crea **más particiones** y mejora la distribución |

---

### Composite Key vs Simple Key

```
Simple Primary Key:
└── Solo Partition Key

Composite Primary Key:
├── Partition Key  → determina la partición
└── Sort Key       → permite múltiples ítems en la misma partición
                     ordenados y consultables eficientemente
```

> El composite key **mejora** el rendimiento al permitir más granularidad en la distribución de datos. Nunca debe evitarse.

---

### Regla mental para el examen

> - **Distribuir workload uniformemente en DynamoDB** → **Partition keys de alta cardinalidad**
> - **Hot partition** = partition key con pocos valores distintos → throughput desperdiciado
> - **Más valores distintos** en la partition key → mejor distribución del I/O
> - **Composite key** (partition + sort) → siempre mejor que simple key para rendimiento
   
&nbsp;   

&nbsp;   

&nbsp;

## Identity Federation con AD Connector + IAM Roles

### Los requisitos del escenario

```
1. Acceso a AWS Console para developers
2. Identity federation (usar identidades existentes, no crear nuevas en AWS)
3. Role-based access control
4. Roles ya asignados via grupos en Active Directory corporativo
```

---

### La solución: AD Connector + IAM Roles

```
Corporate Active Directory (on-premises)
├── Grupos con roles ya definidos
└── Usuarios de developers
         ↓
AWS Directory Service AD Connector
(gateway que redirige requests al AD corporativo)
         ↓
IAM Roles (asignados a usuarios/grupos del AD)
         ↓
Acceso a AWS Console ✅
```

---

### Comparación de opciones de AWS Directory Service

| Servicio | Descripción | ¿Aplica aquí? |
|---|---|---|
| **AD Connector** | Gateway que **redirige** requests al AD on-premises existente | ✅ Integra AD corporativo existente |
| **Simple AD** | AD standalone en AWS con funciones básicas | ❌ No conecta con AD corporativo existente |
| **AWS Managed Microsoft AD** | AD completo administrado por AWS en la nube | ❌ Crea un AD nuevo, no usa el existente |

---

### Por qué las otras opciones son incorrectas

| Opción | Por qué no aplica |
|---|---|
| **Simple AD** | Subconjunto de features, no redirige al AD corporativo. Es un directorio independiente |
| **IAM Groups** | Colección de usuarios IAM. No integra con Active Directory ni soporta federation |
| **AWS Lambda** | Servicio de computación serverless, sin relación con autenticación/identidad |

---

### IAM Roles vs IAM Groups en este contexto

```
IAM Groups                       IAM Roles
──────────                       ─────────
Agrupa usuarios IAM nativos      Puede asignarse a usuarios/grupos
Solo para identidades en AWS     de Active Directory federados ✅
No soporta federation            Soporta identity federation ✅
```

---

### Regla mental para el examen

> - **AD corporativo existente + AWS** → **AD Connector** (no Simple AD)
> - **Identity federation + permisos AWS** → **IAM Roles** (no IAM Groups)
> - **Simple AD** → directorio standalone básico en AWS, sin conexión al AD on-premises
> - **IAM Groups** → solo para usuarios IAM nativos de AWS, no para federation

&nbsp;   

&nbsp;   

&nbsp;

## AWS Transfer for SFTP + S3 + Lifecycle Rules: SFTP Administrado

### Los requisitos del escenario

```
1. Transferencia SFTP de archivos críticos
2. Cifrado en reposo
3. Alta disponibilidad
4. Eliminación automática después de 1 mes
5. Mínimo overhead operacional
```

---

### La solución correcta

```
Clientes SFTP existentes
         ↓ (sin modificar aplicaciones)
AWS Transfer for SFTP endpoint
         ↓
Amazon S3 (encryption enabled)
         ↓
S3 Lifecycle Rule: Expiration action → eliminar objetos después de 30 días ✅
```

---

### Por qué las otras opciones fallan

| Opción | Problema específico |
|---|---|
| **AWS Transfer SFTP + S3 + retention policy en el servidor SFTP** | AWS Transfer for SFTP **no tiene** opción de retention policy. La eliminación debe configurarse en S3 |
| **AWS Transfer SFTP + EFS + EFS lifecycle policy** | EFS lifecycle management **solo transiciona** archivos a/desde la clase Infrequent Access. **No elimina** archivos |
| **EC2 + SFTP manual + EFS + cron job** | Técnicamente posible pero **mayor overhead operacional**: debes gestionar EC2, instalar/mantener SFTP, administrar cron jobs |

---

### S3 Lifecycle: dos tipos de acciones

```
Transition Actions              Expiration Actions
──────────────────              ──────────────────
Mueven objetos entre            ELIMINAN objetos
clases de almacenamiento        automáticamente
S3 Standard → Glacier           después de N días ✅
(reducir costos)                (aplica aquí)
```

---

### AWS Transfer for SFTP: ventaja clave

```
Sin AWS Transfer:                Con AWS Transfer:
├── Necesitas EC2                ├── Fully managed ✅
├── Instalar servidor SFTP       ├── Alta disponibilidad built-in ✅
├── Mantener parches             ├── Clientes SFTP sin cambios ✅
└── Gestionar alta disponibilidad└── Datos directamente en S3 ✅
```

---

### Regla mental para el examen

> - **SFTP + mínimo overhead** → **AWS Transfer for SFTP** (no EC2 + SFTP manual)
> - **Eliminar objetos S3 automáticamente** → **S3 Lifecycle Expiration action**
> - **EFS lifecycle** → solo transiciona a Infrequent Access, **nunca elimina**
> - **Retention policy en AWS Transfer SFTP** → **no existe**, debe configurarse en S3
   
&nbsp;   

&nbsp;   

&nbsp;

## KMS Custom Key Store + CloudHSM: Control Total sobre Claves de Cifrado

### Los tres requisitos específicos del escenario

```
1. Control total sobre el cifrado de las claves
2. Capacidad de eliminar el key material de AWS KMS inmediatamente
3. Auditar el uso de claves independientemente de AWS CloudTrail
```

Estos tres requisitos juntos apuntan a una sola solución: **KMS Custom Key Store + CloudHSM**.

---

### Los tipos de KMS Keys y su nivel de control

| Tipo de Key | ¿Quién la gestiona? | Control del cliente | Auditoría independiente |
|---|---|---|---|
| **AWS Owned Keys** | AWS (completamente) | ❌ Ninguno | ❌ No |
| **AWS Managed Keys** | AWS (automáticamente) | ❌ Limitado | ❌ No |
| **Customer Managed Keys** | Cliente (en KMS estándar) | ✅ Alto | ⚠️ Solo via CloudTrail |
| **Custom Key Store (CloudHSM)** | Cliente (en su propio HSM) | ✅ Total | ✅ Independiente de CloudTrail |

---

### ¿Cómo funciona el Custom Key Store?

```
AWS KMS (front-end)
         ↓ genera y usa keys
Tu propio CloudHSM Cluster
├── Key material NUNCA sale del HSM en texto plano
├── Tú controlas el ciclo de vida de las keys
├── Puedes eliminar key material inmediatamente ✅
└── Auditoría independiente de AWS CloudTrail ✅
```

---

### Por qué las otras opciones fallan

| Opción | Error específico |
|---|---|
| **Custom Key Store + Amazon S3** | S3 es almacenamiento general, no tiene el nivel de seguridad criptográfica de un HSM. No cumple los requisitos de control y auditoría |
| **AWS Owned Keys + CloudHSM** | AWS Owned Keys son gestionadas completamente por AWS → sin control del cliente ❌ |
| **AWS Managed Keys + CloudHSM** | AWS Managed Keys también son gestionadas por AWS → sin auditoría independiente de CloudTrail ❌ |

---

### Cuándo usar Custom Key Store (criterios clave)

```
✅ Necesitas HSM dedicado bajo tu control directo (single-tenancy)
✅ Debes poder revocar/eliminar key material inmediatamente
✅ Compliance requiere auditoría independiente de AWS KMS y CloudTrail
```

---

### Regla mental para el examen

> - **Control total + eliminar key material + auditoría independiente** → **KMS Custom Key Store + CloudHSM**
> - **Keys gestionadas por AWS sin overhead** → **AWS Managed Keys**
> - **Keys del cliente en KMS estándar** → **Customer Managed Keys**
> - **CloudHSM sin KMS** → HSM dedicado para casos que no requieren integración con servicios AWS
> - **Amazon S3** → nunca para almacenar key material criptográfico
   
&nbsp;   

&nbsp;   

&nbsp;

## AWS Storage Gateway File Gateway: Backup Híbrido con SMB y Caché Local

### Los requisitos del escenario

```
1. Protocolo SMB para acceso a documentos
2. Caché local → baja latencia para datos recientes + reducir egress charges
3. Acceso inmediato por 6 meses (minutos)
4. Archivado por 10 años (compliance)
5. Solución costo-efectiva
```

---

### La solución: File Gateway + S3 + Lifecycle → Glacier

```
On-premises (documentos corporativos)
         ↓ SMB protocol ✅
File Gateway (appliance virtual on-premises)
├── Caché local → acceso rápido a datos recientes ✅
├── Reduce data egress (sirve desde caché) ✅
         ↓ almacena en
Amazon S3 Standard (primeros 6 meses, acceso inmediato en minutos) ✅
         ↓ S3 Lifecycle Policy (después de 6 meses)
Amazon S3 Glacier (archivado por 10 años) ✅
```

---

### Tipos de Storage Gateway y sus casos de uso

| Gateway | Protocolo | Caché local | Almacenamiento | Caso de uso |
|---|---|---|---|---|
| **File Gateway** | NFS, **SMB** ✅ | ✅ Sí | S3 | Archivos compartidos híbridos |
| **Tape Gateway** | iSCSI (virtual tape) | ❌ No | S3/Glacier | Backup tipo cinta, no acceso inmediato |
| **Volume Gateway** | iSCSI | ✅ Sí | S3 (snapshots EBS) | Volumes de bloque on-premises |

---

### Por qué las otras opciones fallan

| Opción | Problema específico |
|---|---|
| **Tape Gateway** | No provee acceso inmediato en minutos. Sin caché local → más egress charges |
| **Direct Connect + EBS + Lifecycle** | EBS menos durable que S3. Más costoso. EBS no tiene lifecycle policy nativa hacia Glacier |
| **AWS DataSync + S3 + Lifecycle** | DataSync es para migración/transferencia masiva. **Sin caché local** → mayor latencia y más egress charges |

---

### Regla mental para el examen

> - **Acceso SMB + caché local + backup en S3** → **File Gateway**
> - **Backup tipo cinta virtual** → **Tape Gateway** (pero sin acceso inmediato)
> - **Acceso iSCSI a volumes en S3** → **Volume Gateway**
> - **Migración masiva de datos** (sin caché) → **AWS DataSync**
> - **Archivado largo plazo después de período activo** → **S3 Lifecycle → Glacier**
   
&nbsp;   

&nbsp;   

&nbsp;

## RDS Multi-AZ: Replicación Síncrona para Alta Disponibilidad

Esta pregunta evalúa una distinción fundamental que ya hemos visto en conversaciones anteriores, pero aquí va el resumen preciso:

### La distinción clave: Síncrono vs Asíncrono

```
Multi-AZ (Síncrono)              Read Replica (Asíncrono)
───────────────────              ─────────────────────────
Escribe en primario              Escribe en primario
    ↓ simultáneamente                ↓ después
Escribe en standby               Replica en segundo plano
→ Ambos siempre en sync ✅       → Puede haber lag ⚠️
→ Failover automático            → Promoción manual
→ Alta disponibilidad            → Escalar lecturas
```

---

### Por qué las otras opciones son incorrectas

| Opción | Error |
|---|---|
| **RDS Read Replica** | Replicación **asíncrona**, no síncrona. Para escalar lecturas, no para HA |
| **DynamoDB Read Replica** | DynamoDB **no tiene** Read Replicas. Usa Global Tables para replicación multi-región |
| **CloudFront Multi-AZ** | CloudFront **no tiene** Multi-AZ ni replica datos de base de datos. Es una CDN que cachea contenido en edge locations |

---

### Regla mental para el examen

> - **Replicación síncrona + failover automático** → **RDS Multi-AZ**
> - **Replicación asíncrona + escalar lecturas** → **RDS Read Replica**
> - **Replicación multi-región en DynamoDB** → **Global Tables**

&nbsp;   

&nbsp;   

&nbsp;

## S3 Versioning + MFA Delete: Protección contra Borrado Accidental

### Los dos mecanismos de protección correctos

**1. Versioning → preserva todas las versiones**
```
Sin Versioning:
DELETE objeto.txt → objeto desaparecido para siempre ❌

Con Versioning:
DELETE objeto.txt → S3 agrega un "delete marker"
                    versiones anteriores siguen existiendo ✅
                    → puedes restaurar eliminando el delete marker
```

**2. MFA Delete → capa adicional de seguridad**
```
Para operaciones destructivas irreversibles se requiere:
├── Credenciales de seguridad normales
└── Código de 6 dígitos del dispositivo MFA físico

Protege contra:
├── Cambiar el estado de Versioning del bucket
└── Eliminar permanentemente una versión de objeto
```

---

### Por qué las otras opciones no cumplen el requisito

| Opción | Por qué falla |
|---|---|
| **IAM bucket policy que niega Delete** | Bloquea **todos** los deletes, incluyendo los intencionales. El requisito es proteger contra accidentales, no prohibir todos |
| **Pre-signed URLs solamente** | Controla acceso temporal a objetos, no previene borrados accidentales |
| **S3 Intelligent-Tiering** | Optimiza costos moviendo datos entre clases de storage. No tiene relación con protección contra borrado |

---

### La combinación correcta y por qué funciona juntos

```
Versioning                       MFA Delete
──────────                       ──────────
Guarda todas las versiones       Requiere MFA para eliminar
Permite recuperar objetos        versiones permanentemente
borrados accidentalmente         
Primera línea de defensa ✅      Segunda línea de defensa ✅
```

---

### Regla mental para el examen

> - **Recuperar objetos borrados/sobreescritos accidentalmente** → **Versioning**
> - **Prevenir borrado permanente sin autorización fuerte** → **MFA Delete**
> - Ambos juntos = protección completa contra borrado accidental e intencional no autorizado
> - **Pre-signed URLs** → acceso temporal controlado, no protección contra borrado
> - **IAM Deny Delete** → demasiado restrictivo, bloquea también borrados legítimos
   
&nbsp;   

&nbsp;   

&nbsp;

## AWS WAF + Firewall Manager: Protección SQL Injection Multi-Cuenta

### Los dos requisitos del escenario

```
1. Bloquear SQL injection attacks en ALBs
2. Aplicar la protección en múltiples cuentas AWS
```

---

### La solución: WAF + Firewall Manager

```
AWS WAF
├── Managed Rule: AWSManagedRulesSQLiRuleSet
│   └── Bloquea patrones de SQL injection ✅
├── Asociado al Application Load Balancer
└── Web ACL con acción: BLOCK

          +

AWS Firewall Manager
└── Centraliza y reutiliza las reglas WAF
    en todas las cuentas AWS de la organización ✅
```

---

### Por qué las otras opciones fallan

| Opción | Servicio mal usado | Error específico |
|---|---|---|
| **Network Firewall + refactorizar** | Network Firewall protege VPCs, no ALBs específicamente. Refactorizar requiere tiempo enorme | ❌ No es solución inmediata |
| **GuardDuty + Security Hub** | GuardDuty es **detección de amenazas**, no puede asociarse a un ALB ni bloquear tráfico | ❌ No bloquea, solo detecta |
| **Macie + Audit Manager** | Macie protege **datos sensibles en S3**. Audit Manager es para compliance/auditoría, no seguridad de red | ❌ Servicios completamente irrelevantes |

---

### Mapa de servicios de seguridad AWS

```
Capa de aplicación (HTTP/SQL injection/XSS)  → AWS WAF
Capa de red/VPC (firewall stateful)          → AWS Network Firewall
Ataques DDoS volumétricos                    → AWS Shield Advanced
Detección de amenazas con ML                 → Amazon GuardDuty
Datos sensibles en S3 (PII)                  → Amazon Macie
Gestión centralizada multi-cuenta de WAF     → AWS Firewall Manager
Auditoría de compliance                      → AWS Audit Manager
```

---

### Regla mental para el examen

> - **SQL injection / XSS + ALB/CloudFront/API GW** → **AWS WAF**
> - **Reutilizar reglas WAF en múltiples cuentas** → **AWS Firewall Manager**
> - **GuardDuty** → detecta, nunca bloquea directamente
> - **Network Firewall** → protege VPCs, no específicamente ALBs
> - **Macie** → siempre relacionado con datos sensibles en S3, nunca con ataques web
   
&nbsp;   

&nbsp;   

&nbsp;

## Aurora Auto Scaling: Escalado Dinámico de Read Replicas

### El problema del escenario

```
Tráfico de lectura aumenta durante peak periods
         ↓
Read replica única no puede manejar la carga
         ↓
Performance bottleneck ❌
```

Solución necesaria: **escalar las read replicas dinámicamente según demanda**.

---

### ¿Por qué Aurora Auto Scaling es la respuesta?

```
Tráfico bajo (off-peak)          Tráfico alto (peak)
─────────────────────            ───────────────────
Aurora Auto Scaling              Aurora Auto Scaling
reduce réplicas ✅                agrega réplicas automáticamente ✅
→ Pagas solo lo necesario        → Maneja el tráfico sin bottleneck

Sin intervención manual ✅
Sin over-provisioning ✅
Costo-efectivo ✅
```

---

### Por qué las otras opciones no son costo-efectivas

| Opción | Por qué falla |
|---|---|
| **Aumentar tamaño del cluster** | Escalado **estático** → pagas el tamaño mayor siempre, incluso en off-peak. No es costo-efectivo |
| **Aurora Global Database** | Diseñado para aplicaciones **multi-región globales**. Más complejo y costoso. El problema es local, no global |
| **Read replica en otra región** | Incurre en costos de **replicación inter-región**. El problema no es de disponibilidad cross-region sino de capacidad local |

---

### Comparación de soluciones de escalado en Aurora

```
Aurora Auto Scaling          Aurora Global Database       Aumentar instancia
───────────────────          ──────────────────────       ─────────────────
Escala réplicas              Multi-región                 Escala vertical
dinámicamente                para baja latencia global    estática
Dentro de una región         Cross-region                 Sin flexibilidad
Costo variable ✅            Costo fijo + transfer ❌     Costo fijo ❌
```

---

### Regla mental para el examen

> - **Read traffic spike + costo-efectivo + una región** → **Aurora Auto Scaling**
> - **Baja latencia global + multi-región** → **Aurora Global Database**
> - **Disaster recovery RPO/RTO estricto** → **Aurora Global Database**
> - **Escalar verticalmente** → casi nunca es la respuesta más costo-efectiva en el examen
   
&nbsp;   

&nbsp;   

&nbsp;

## AWS Glue + EventBridge: ETL Automatizado CSV → Parquet

### Los requisitos del escenario

```
1. Convertir archivos CSV (2 GB) → Apache Parquet
2. Trigger automático al subir cada archivo nuevo
3. Mínimo overhead operacional
```

---

### La solución correcta

```
Nuevo archivo .csv subido a S3
         ↓ S3 Object Created event
Amazon EventBridge rule
         ↓ trigger inmediato
AWS Glue ETL Job
├── Lee .csv desde S3 origen
├── Convierte a Apache Parquet
└── Guarda en S3 destino ✅
```

---

### Por qué AWS Glue es mejor que Lambda para este caso

| Criterio | AWS Lambda | AWS Glue ETL |
|---|---|---|
| **Límite de tiempo** | 15 minutos máximo ❌ | Sin límite práctico ✅ |
| **Límite de memoria** | 10 GB máximo ❌ | Escala automáticamente ✅ |
| **Archivos de 2 GB** | Problemático (timeouts) ❌ | Diseñado para big data ✅ |
| **Conversión a Parquet** | Requiere librerías adicionales | Soporte nativo ✅ |
| **Overhead operacional** | Bajo | Muy bajo ✅ |

---

### Por qué las otras opciones fallan

| Opción | Problema específico |
|---|---|
| **Glue crawler en schedule (cada hora)** | No es event-driven. El trigger es por tiempo, no por upload. Archivos esperan hasta el próximo ciclo |
| **Lambda + AWS Transfer Family SFTP** | Lambda tiene límites de tiempo/memoria para 2 GB. SFTP innecesario para mover archivos entre buckets S3 |
| **Spark en EC2 + EventBridge + Lambda Function URL** | Máximo overhead: provisionar EC2, instalar Spark, mantener infraestructura. Contradice "least operational overhead" |

---

### Schedule vs Event-Driven: distinción clave

```
Glue Crawler en schedule (cada hora)    EventBridge → Glue (event-driven)
────────────────────────────────        ──────────────────────────────────
Revisa si hay archivos nuevos           Se dispara INMEDIATAMENTE
cada 60 minutos                         al detectar el upload
Latencia: hasta 59 minutos ❌           Latencia: segundos ✅
Procesa aunque no haya nuevos archivos  Solo procesa cuando hay evento
```

---

### Regla mental para el examen

> - **ETL de archivos grandes + conversión de formato** → **AWS Glue**
> - **Trigger inmediato al subir archivo a S3** → **EventBridge (S3 Object Created)**
> - **Lambda para ETL** → solo para archivos pequeños (límite 15 min / 10 GB)
> - **Glue Crawler en schedule** → descubre schema, no es ideal para triggers de procesamiento
> - **Apache Parquet** → formato columnar optimizado para big data y consultas analíticas

&nbsp;   

&nbsp;   

&nbsp;

## Auto Scaling Default Termination Policy: ¿Cuál instancia se elimina primero?

### El flujo de decisión por defecto

```
Scale-in triggered
         ↓
1. ¿Cuál AZ tiene MÁS instancias?
   → Selecciona esa AZ (para balancear entre zonas)
         ↓
2. En esa AZ, ¿cuál instancia usa el LAUNCH TEMPLATE MÁS ANTIGUO?
   → Selecciona esa instancia ✅
         ↓
3. Si hay empate, ¿cuál está más cerca de su próxima hora de facturación?
   → Termina esa (maximiza el uso pagado)
         ↓
4. Si aún hay empate → selección ALEATORIA
```

---

### Por qué las otras opciones son incorrectas

| Opción | Por qué falla |
|---|---|
| **Menos sesiones de usuario** | ASG no monitorea sesiones de usuarios como criterio de terminación |
| **Corriendo por más tiempo** | La antigüedad de ejecución no es el criterio principal (es el launch template más antiguo) |
| **Selección aleatoria** | Solo ocurre en el paso 4 como último recurso, no es el comportamiento primario |

---

### El propósito de cada paso

```
Paso 1 (balancear AZs)        → Mantener arquitectura distribuida uniformemente
Paso 2 (launch template viejo) → Priorizar actualización a configuraciones nuevas
Paso 3 (hora de facturación)  → Optimizar costos (no desperdiciar tiempo pagado)
Paso 4 (aleatorio)            → Desempate final
```

---

### Regla mental para el examen

> En el default termination policy de Auto Scaling, el orden de prioridad es:
> 1. **AZ con más instancias** (balanceo)
> 2. **Launch template más antiguo** (actualización)
> 3. **Más cercana a la hora de facturación** (optimización de costos)
> 4. **Aleatoria** (último recurso)
   
&nbsp;   

&nbsp;   

&nbsp;

## Identity Federation + IAM Roles: SSO para 1200 Usuarios en S3

### Los requisitos del escenario

```
1. Single Sign-On desde AD/LDAP corporativo (no crear nuevas identidades AWS)
2. Acceso restringido a carpeta individual por usuario en S3
3. Solución para 1200 empleados
```

---

### Las dos respuestas correctas

**1. Federation Proxy / Identity Provider + AWS STS**
```
Usuario corporativo
         ↓ credenciales AD/LDAP
Identity Provider (IdP) / Federation Proxy
         ↓ autenticación exitosa
AWS STS (Security Token Service)
         ↓ genera credenciales temporales
Acceso a AWS (S3) sin crear IAM users ✅
```

**2. IAM Role + IAM Policy**
```
IAM Policy con variable de política:
{
  "Resource": "arn:aws:s3:::bucket/${aws:username}/*"
                                    ↑
                          Variable dinámica por usuario
}
→ Cada usuario accede SOLO a su carpeta ✅
```

---

### Por qué las otras opciones son incorrectas

| Opción | Por qué falla |
|---|---|
| **Soluciones SSO de terceros (Okta, etc.)** | AWS ya provee las herramientas necesarias (STS + Federation). No es necesario pagar por soluciones externas |
| **Amazon WorkDocs** | Servicio de colaboración de documentos, no tiene integración directa con S3 para este caso |
| **Crear 1200 IAM Users** | Innecesario y no integra con AD/LDAP corporativo. Viola el requisito de SSO |

---

### El flujo completo de Enterprise Identity Federation

```
AD/LDAP corporativo
         ↓ SAML 2.0 / OpenID Connect
Federation Proxy o IdP (ej: AD FS)
         ↓
AWS STS → AssumeRoleWithSAML
         ↓ credenciales temporales
IAM Role (con policy que usa ${aws:username})
         ↓
S3 bucket/nombreusuario/* (solo su carpeta) ✅
```

---

### Regla mental para el examen

> - **SSO + AD/LDAP corporativo + AWS** → **Federation + STS** (no crear IAM Users)
> - **Restringir acceso por usuario en S3** → **IAM Policy con variables** (`${aws:username}`)
> - **1200+ usuarios** → nunca crear IAM Users individuales (no escala, no integra con AD)
> - **STS** → siempre genera credenciales **temporales** (no permanentes)
   
&nbsp;   

&nbsp;   

&nbsp;

## AWS DMS con CDC + SSL: Migración y Replicación Continua

### Los requisitos del escenario

```
1. Copiar MySQL on-premises → S3 como CSV (carga inicial)
2. Capturar cambios continuos después de la migración (ongoing)
3. Alta seguridad (conexiones cifradas)
4. Poco overhead de gestión
```

---

### La solución correcta: DMS Full Load + CDC + SSL

```
MySQL on-premises
         ↓ Full Load (carga inicial completa)
         ↓ + CDC (Change Data Capture - cambios continuos)
AWS DMS con endpoint SSL
├── Certificado CA propio añadido a DMS console
├── Conexión cifrada TLS ✅
└── Salida en formato .csv por defecto ✅
         ↓
Amazon S3 bucket (CSV files)
         ↓ (futuro)
Aurora Serverless + RDS Proxy
```

---

### Full Load vs CDC: roles distintos pero complementarios

```
Full Load                        CDC (Change Data Capture)
──────────                       ─────────────────────────
Copia TODOS los datos            Captura SOLO los cambios
existentes al inicio             después de la carga inicial
Migración inicial ✅             Sincronización continua ✅
Una sola vez                     Streaming permanente
```

> La pregunta requiere **ambos** en la misma tarea DMS.

---

### Por qué las otras opciones fallan

| Opción | Error específico |
|---|---|
| **DMS Full Load únicamente + Network Firewall para SSL** | Sin CDC → no captura cambios continuos. Network Firewall no crea certificados DMS, eso se hace directo en la consola DMS |
| **SCT + AWS MGN** | SCT convierte esquemas, no replica datos. MGN es para lift-and-shift de aplicaciones completas, no para replicación de DB |
| **Snowball Edge + DataSync** | Snowball es para migraciones masivas físicas. DataSync para replicación requiere pasos extra innecesarios cuando DMS lo hace directamente |

---

### Regla mental para el examen

> - **Migrar DB + capturar cambios continuos** → **DMS Full Load + CDC**
> - **Cifrar conexiones DMS** → **SSL con CA certificate** (no Network Firewall)
> - **Convertir esquema entre motores** → **AWS SCT** (heterogéneo)
> - **Migrar servidores completos (lift-and-shift)** → **AWS MGN**
> - **DMS → S3** genera archivos **.csv por defecto** (también soporta Parquet)
   
&nbsp;   

&nbsp;   

&nbsp;

## SQS FIFO vs Standard: Eliminando Mensajes Duplicados

### El problema raíz

```
SQS Standard Queue
├── Entrega "at-least-once" → puede entregar el mismo mensaje MÁS DE UNA VEZ
├── Sin garantía de orden
└── Si EC2 falla antes de eliminar el mensaje → mensaje reaparece → procesado dos veces ❌
```

---

### La solución: SQS FIFO Queue

```
SQS FIFO Queue
├── Entrega "exactly-once" → cada mensaje procesado UNA SOLA VEZ ✅
├── Orden garantizado (First-In-First-Out) ✅
├── Deduplicación automática de mensajes
└── Ideal para: pedidos, transacciones financieras, comandos secuenciales
```

---

### Por qué las otras opciones no resuelven el problema

| Opción | Qué hace realmente | ¿Resuelve duplicados? |
|---|---|---|
| **Visibility timeout** | Oculta el mensaje mientras se procesa | ❌ No garantiza contra duplicados en Standard queue |
| **Retention period** | Define cuánto tiempo existe el mensaje en la cola | ❌ No tiene relación con duplicados |
| **Message size** | Límite de tamaño del mensaje (256 KB) | ❌ Completamente irrelevante |
| **FIFO Queue** | Exactly-once + orden garantizado | ✅ Elimina duplicados |

---

### Standard vs FIFO: comparación directa

```
SQS Standard                     SQS FIFO
────────────                      ─────────
At-least-once delivery ❌         Exactly-once delivery ✅
Sin orden garantizado             Orden garantizado (FIFO)
Throughput ilimitado              300 msg/s (3,000 con batching)
Más barato                        Ligeramente más costoso
Para alta escala sin importar     Para orden y no-duplicación
duplicados                        críticos
```

---

### Regla mental para el examen

> - **Mensajes duplicados en SQS** → **FIFO Queue** (exactly-once delivery)
> - **Orden de procesamiento crítico** → **FIFO Queue**
> - **Máximo throughput sin importar duplicados** → **Standard Queue**
> - **Visibility timeout** → evita que otros consumidores vean el mensaje, pero NO elimina duplicados
   
&nbsp;   

&nbsp;   

&nbsp;

## Amazon Neptune + Neptune Streams: Base de Datos de Grafos para Recomendaciones

### Los requisitos del escenario

```
1. Almacenar datos con relaciones complejas (interacciones, preferencias, patrones)
2. Motor de recomendaciones basado en comportamiento de usuarios
3. Rastrear cambios en la base de datos dinámicamente
4. Mínimo overhead operacional
```

---

### ¿Por qué Neptune es la elección correcta?

```
Datos de relaciones complejas:
Usuario → compró → Producto A
Usuario → vio → Producto B
Usuario → es amigo de → Usuario 2
Usuario 2 → compró → Producto C
         ↓
Neptune (Graph Database) → consultas en milisegundos sobre billones de relaciones ✅
```

**Neptune Streams** para cambios en tiempo real:
```
Cambio en el grafo (nueva compra, nueva relación)
         ↓
Neptune Streams captura y registra CADA cambio
en orden cronológico ✅
         ↓
Accesible via HTTP REST API
         ↓
Motor de recomendaciones actualizado en tiempo real ✅
```

---

### Por qué las otras opciones fallan

| Opción | Problema específico |
|---|---|
| **Aurora PostgreSQL + Kinesis** | Aurora es relacional, no optimizado para datos de grafos. Kinesis añade complejidad operacional innecesaria |
| **Neptune + Kinesis Data Streams** | Kinesis no entiende las relaciones de grafo nativamente. Neptune Streams está diseñado específicamente para datos de grafo |
| **Amazon Keyspaces + Neptune Streams** | Keyspaces es compatible con Cassandra (NoSQL columnar), no es una base de datos de grafos. Neptune Streams solo funciona con Neptune |

---

### Mapa de bases de datos especializadas en AWS

```
Relacional (SQL)          → RDS, Aurora
NoSQL clave-valor         → DynamoDB
NoSQL columnar            → Amazon Keyspaces (Cassandra)
Grafos (relaciones)       → Amazon Neptune ✅
Time-series               → Amazon Timestream
Documentos                → Amazon DocumentDB
En memoria (caché)        → ElastiCache
Data warehouse (OLAP)     → Amazon Redshift
```

---

### Regla mental para el examen

> - **Relaciones complejas + redes sociales + motores de recomendación + detección de fraude** → **Amazon Neptune**
> - **Cambios en tiempo real en Neptune** → **Neptune Streams** (no Kinesis)
> - **Kinesis** → streaming de datos externos, no cambios internos de grafo
> - Cuando el problema menciona "relaciones entre entidades" o "grafos" → siempre **Neptune**
   
&nbsp;   

&nbsp;   

&nbsp;

## EC2 Billing: Cuándo se Cobra y Cuándo No

### Mapa de estados EC2 y su facturación

```
pending      → ❌ NO se cobra (preparando para ejecutar)
running      → ✅ SÍ se cobra (estado normal de operación)
stopping     → ⚠️ DEPENDE:
               ├── Preparando para STOP    → ❌ NO se cobra
               └── Preparando para HIBERNATE → ✅ SÍ se cobra
stopped      → ❌ NO se cobra (apagado)
shutting-down → ❌ NO se cobra (preparando para terminar)
terminated   → ⚠️ DEPENDE del tipo:
               ├── On-Demand terminada     → ❌ NO se cobra
               └── Reserved Instance terminada → ✅ SÍ se cobra
                   (hasta el fin del término contratado)
```

---

### Las dos respuestas correctas explicadas

**✅ On-Demand en `stopping` preparando para hibernar → SE COBRA**
> Durante hibernación, el contenido de RAM se guarda en el volumen EBS. La instancia mantiene su estado y sigue incurriendo en cargos durante este proceso.

**✅ Reserved Instance en estado `terminated` → SE COBRA**
> Las Reserved Instances se pagan por contrato (1 o 3 años). Aunque la instancia se termine, el compromiso de pago continúa hasta el fin del término.

---

### Por qué las otras opciones son incorrectas

| Opción | Por qué es falsa |
|---|---|
| **Spot instance en `stopping`** | No se cobra cuando se prepara para detenerse |
| **On-Demand en `pending`** | Pending es solo preparación inicial, sin cargo |
| **"No se cobra si no está en `running`"** | Falso: hibernación (`stopping`) y Reserved terminadas sí se cobran |

---

### Regla mental para el examen

> - **`stopping` → stop** = no se cobra
> - **`stopping` → hibernate** = sí se cobra
> - **Reserved Instance terminada** = sigue cobrándose hasta fin del contrato
> - **`pending`, `stopped`, `shutting-down`** = no se cobra en On-Demand/Spot
   
&nbsp;   

&nbsp;   

&nbsp;

## S3 + DynamoDB: Solución Costo-Efectiva para Base de Datos GIS

### Los requisitos del escenario

```
1. Almacenar imágenes de alta resolución con códigos geográficos
2. Actualizaciones frecuentes (minuto a minuto)
3. Alta disponibilidad y escalabilidad
4. Migrar desde Oracle
5. Costo-efectivo
```

---

### La solución correcta: S3 + DynamoDB

```
Imagen de alta resolución → Amazon S3 (object storage) ✅
                                    ↓ URL del objeto
DynamoDB Table:
┌─────────────────┬──────────────────────────────┐
│ geographic_code │ image_s3_url                 │
│ (Primary Key)   │ (valor asociado)             │
├─────────────────┼──────────────────────────────┤
│ GEO-LAT123      │ s3://bucket/imagen-123.tif   │
│ GEO-LAT456      │ s3://bucket/imagen-456.tif   │
└─────────────────┴──────────────────────────────┘
```

**¿Por qué esta combinación?**
- S3 → almacenamiento ilimitado y económico para imágenes grandes
- DynamoDB → clave-valor de baja latencia, altamente escalable, sin servidor que gestionar

---

### Por qué las otras opciones fallan

| Opción | Error específico |
|---|---|
| **RDS Oracle Multi-AZ** | Almacenar imágenes como BLOBs en Oracle es costoso (licencias Oracle + instancias grandes). S3 es mucho más económico para objetos estáticos |
| **S3 + Amazon Keyspaces (Cassandra)** | Keyspaces es para datos de alta velocidad con esquemas flexibles. DynamoDB es más adecuado para este simple caso de clave-valor |
| **DynamoDB + DAX para imágenes** | ❌ Dos problemas: (1) Las imágenes de alta resolución exceden el límite de 400 KB por ítem en DynamoDB. (2) DAX optimiza **lecturas**, pero el sistema es **write-intensive** → innecesario y costoso |

---

### Límites importantes de DynamoDB a recordar

```
Tamaño máximo por ítem: 400 KB
→ Nunca almacenes imágenes/archivos grandes directamente en DynamoDB
→ Solución correcta: S3 para el objeto + DynamoDB para la referencia (URL)
```

---

### Regla mental para el examen

> - **Imágenes/archivos grandes** → siempre en **S3**, nunca directamente en DynamoDB
> - **Referencia/metadata de objetos S3** → **DynamoDB** (clave-valor rápido)
> - **DAX** → solo justificado para sistemas **read-heavy**, no write-intensive
> - **Keyspaces** → esquemas flexibles y alta velocidad, no simple clave-valor
> - **Oracle en RDS** → costoso por licencias; migrar a servicios nativos AWS ahorra dinero
   
&nbsp;   

&nbsp;   

&nbsp;

Esta es una pregunta conceptual directa. Aquí el resumen:

### Respuesta: AWS Storage Gateway

Es el servicio diseñado específicamente para **extender infraestructura on-premises hacia la nube AWS**, actuando como puente entre ambos entornos.

---

### Por qué las otras opciones no aplican

| Servicio | Propósito real |
|---|---|
| **Amazon EC2** | Servicio de **cómputo** (servidores virtuales), no storage |
| **Amazon EBS** | Block storage **exclusivo para instancias EC2**, no extiende on-premises |
| **Amazon SQS** | Servicio de **colas de mensajes**, sin relación con storage |
| **AWS Storage Gateway** | ✅ Conecta on-premises con cloud storage de forma transparente |

---

### Regla mental para el examen

> - **Extender storage on-premises hacia AWS** → **AWS Storage Gateway**
> - Los tres tipos de Gateway (File, Tape, Volume) cubren diferentes casos de uso, pero todos resuelven la integración híbrida on-premises ↔ AWS
   
&nbsp;   

&nbsp;   

&nbsp;

## Route 53 Geoproximity Routing: Control de Cobertura Geográfica

### La distinción clave del escenario

El requisito no es simplemente "enrutar por ubicación" sino **controlar qué tan grande es el área geográfica** que se enruta a cada región. Eso requiere **bias**.

---

### Geoproximity Routing + Bias

```
Sin bias (default):
├── Filipinas → Sydney (más cercano geográficamente)
└── India Norte → Sydney o Tokyo (similar distancia)

Con bias positivo en Tokyo:
├── Bias +X en ap-northeast-1 (Tokyo) → expande su área de cobertura
└── Filipinas Norte + India Norte → ahora enrutados a Tokyo ✅
```

```
Bias positivo  → EXPANDE la región geográfica del recurso (atrae más tráfico)
Bias negativo  → REDUCE la región geográfica del recurso (atrae menos tráfico)
```

---

### Comparación de políticas de routing relevantes

| Política | Basada en | Control de cobertura | Caso de uso |
|---|---|---|---|
| **Geoproximity** | Ubicación usuario + recurso | ✅ Sí (con bias) | Ajustar áreas de cobertura ✅ |
| **Geolocation** | Ubicación del usuario | ❌ No (fija por país/continente) | Enrutar por país específico |
| **Latency** | Menor latencia a la región | ❌ No | Mejor performance |
| **Weighted** | Porcentaje de tráfico | ❌ No (no geográfico) | A/B testing, load balancing |

---

### Por qué Geolocation no funciona aquí

```
Geolocation Routing:
├── Filipinas → asignado a una región fija
└── India → asignado a una región fija
❌ No puedes expandir/contraer la cobertura
❌ No puedes enrutar "parte norte de Filipinas" a Tokyo
   y "parte sur" a Sydney
```

---

### Regla mental para el examen

> - **Controlar el tamaño del área geográfica** que va a cada recurso → **Geoproximity + bias**
> - **Enrutar por país/continente específico** (sin ajuste de cobertura) → **Geolocation**
> - **Menor latencia** → **Latency Routing**
> - **Dividir tráfico en porcentajes** → **Weighted Routing**
> - **Bias positivo** = más cobertura; **Bias negativo** = menos cobertura
   
&nbsp;   

&nbsp;   

&nbsp;

## AWS DataSync + S3 Glacier Deep Archive: Migración de Datos Históricos

### El problema del escenario

```
On-premises storage casi lleno
├── Datos activos → deben quedarse on-premises
└── Datos históricos (cold data) → mover a AWS
                                   para liberar espacio
```

---

### La solución correcta: DataSync → S3 Glacier Deep Archive directo

```
On-premises (datos históricos)
         ↓
AWS DataSync
├── Velocidad hasta 10x mayor que herramientas open-source
├── Maneja scripting, scheduling, monitoreo automáticamente
├── Sin modificar aplicaciones existentes
└── Transferencia directa a Glacier Deep Archive ✅
         ↓
S3 Glacier Deep Archive (costo mínimo para archivado)
```

---

### Por qué las otras opciones son incorrectas

| Opción | Problema específico |
|---|---|
| **Storage Gateway → Glacier Deep Archive** | Storage Gateway está diseñado para **acceso híbrido continuo con caché**, no para migración masiva de datos históricos |
| **Storage Gateway → Glacier → lifecycle a Deep Archive** | Mismo problema + pasos innecesarios adicionales |
| **DataSync → S3 Standard → lifecycle → Glacier Deep Archive (30 días)** | DataSync puede ir **directamente** a Glacier Deep Archive. No necesitas S3 Standard + esperar 30 días |

---

### DataSync vs Storage Gateway: distinción clave

```
AWS DataSync                     AWS Storage Gateway
────────────                     ───────────────────
Migración/transferencia          Integración híbrida continua
masiva de datos                  on-premises ↔ AWS
One-time o periódica             Acceso permanente con caché local
Hasta 10x más rápido             Optimiza cambios incrementales
Para mover datos fríos/históricos Para acceder datos activos en nube
```

---

### Regla mental para el examen

> - **Mover datos históricos/fríos de on-premises a AWS** → **AWS DataSync**
> - **Acceso híbrido continuo con caché local** → **AWS Storage Gateway**
> - **Archivado de largo plazo más económico en S3** → **S3 Glacier Deep Archive**
> - DataSync puede escribir **directamente** en Glacier Deep Archive sin pasar por S3 Standard
   
&nbsp;   

&nbsp;   

&nbsp;

## Route 53 Failover: Active-Active vs Active-Passive

### La distinción fundamental

```
Active-Active Failover           Active-Passive Failover
─────────────────────            ───────────────────────
TODOS los recursos activos       Recursos PRIMARIOS activos
simultáneamente                  Recursos SECUNDARIOS en standby
                                 
Route 53 responde con            Route 53 responde solo con
cualquier recurso saludable      recursos primarios saludables
                                 Si todos fallan → usa secundarios
Política: Weighted, Latency,     Política: Failover (routing policy)
Geolocation, etc.
```

---

### ¿Por qué Active-Active con Weighted policy es correcto?

El escenario requiere que **todos los recursos estén disponibles todo el tiempo**:

```
Región us-east-1 (activa)  ──┐
Región eu-west-1 (activa)  ──┼──→ Route 53 (Weighted) → distribuye tráfico
Región ap-northeast-1(activa)┘     entre todos los saludables

Si una región falla → Route 53 detecta el health check fallido
                   → excluye esa región automáticamente
                   → tráfico continúa a las regiones saludables ✅
```

---

### Por qué las otras opciones son incorrectas

| Opción | Por qué falla |
|---|---|
| **Active-Passive con Weighted Records** | Active-Passive tiene primarios y secundarios. El requisito es que TODOS estén activos siempre |
| **Active-Passive con múltiples primarios y secundarios** | Mismo problema: hay recursos en standby, no todos activos simultáneamente |
| **Active-Active con un primario y un secundario** | Concepto inválido: Active-Active no tiene primarios ni secundarios. Todos son iguales |

---

### Regla mental para el examen

> - **"Todos los recursos disponibles todo el tiempo"** → **Active-Active Failover**
> - **"Recurso primario con backup en standby"** → **Active-Passive Failover**
> - Active-Active usa: Weighted, Latency, Geolocation (cualquier política excepto Failover)
> - Active-Passive usa: **Failover routing policy** específicamente
> - En Active-Active **no existen** conceptos de "primario" y "secundario"
   
&nbsp;   

&nbsp;   

&nbsp;

## Elastic IP + Network Load Balancer: IPs Estáticas para Whitelist

### El problema del escenario

```
Clientes on-premises tienen firewalls con whitelist de IPs
         ↓
Necesitan una IP fija y confiable para agregar a su whitelist
         ↓
Los load balancers normalmente tienen IPs dinámicas que cambian
```

---

### La solución: EIP + Network Load Balancer

```
Clientes on-premises
(whitelist: IP fija conocida)
         ↓
Elastic IP (estática, nunca cambia) ✅
         ↓
Network Load Balancer (NLB) ← único LB que acepta EIP
         ↓
EC2 instances (backend)
```

---

### ¿Por qué NLB y no ALB?

| Load Balancer | Capa OSI | ¿Acepta Elastic IP? | Protocolo |
|---|---|---|---|
| **Application LB (ALB)** | Capa 7 (HTTP/HTTPS) | ❌ No | HTTP, HTTPS, gRPC |
| **Network LB (NLB)** | Capa 4 (TCP/UDP) | ✅ Sí | TCP, UDP, TLS |
| **Gateway LB** | Capa 3 | ❌ No | IP |

> Si necesitas EIP en un ALB → pon un NLB **delante** del ALB.

---

### Por qué las otras opciones fallan

| Opción | Error |
|---|---|
| **EIP en ALB** | ALB **no acepta** Elastic IP. Las IPs del ALB son dinámicas |
| **CloudFront con IPs privadas** | CloudFront no resuelve el problema de IPs fijas en whitelist. Además no apunta a IPs privadas directamente |
| **Route 53 Alias Record** | El DNS sigue resolviendo a IPs dinámicas del LB. Los clientes aún no pueden whitelistear una IP fija |

---

### Regla mental para el examen

> - **IP estática/fija para whitelist en un load balancer** → **EIP + Network Load Balancer**
> - **ALB nunca acepta EIP** → usa NLB delante si necesitas IP estática con ALB
> - **NLB** = capa 4, millones de requests/segundo, IP estática posible
> - **ALB** = capa 7, routing basado en contenido HTTP, sin EIP
   
&nbsp;   

&nbsp;   

&nbsp;

## ElastiCache Memcached + Auto Discovery: Gestión Distribuida de Sesiones

### Los requisitos específicos del escenario

```
1. Sesiones compartidas entre múltiples instancias ← distribuido
2. Rendimiento multithreaded                       ← clave
3. Detección automática de fallos de nodos         ← Auto Discovery
4. Reemplazo automático de nodos fallidos          ← Auto Discovery
5. Latencia sub-millisegundo                       ← caché en memoria
```

---

### ¿Por qué Memcached con Auto Discovery?

**Auto Discovery** resuelve los requisitos 3 y 4:
```
Sin Auto Discovery:
├── App conecta manualmente a cada nodo
├── Si un nodo falla → conexión rota
└── Requiere intervención manual

Con Auto Discovery:
├── App conecta a UN nodo → obtiene lista de TODOS
├── Nodos fallidos detectados automáticamente ✅
├── Nodos fallidos reemplazados automáticamente ✅
└── Sin hardcodear endpoints individuales
```

---

### Memcached vs Redis para este caso

| Característica | Memcached | Redis |
|---|---|---|
| **Multithreaded** | ✅ Sí (nativo) | ❌ Single-threaded por defecto |
| **Auto Discovery** | ✅ Sí | ❌ No |
| **Reemplazo automático de nodos** | ✅ Sí | ❌ No automático |
| **Latencia sub-ms** | ✅ Sí | ✅ Sí |
| **Persistencia de datos** | ❌ No | ✅ Sí |
| **Estructuras de datos complejas** | ❌ No | ✅ Sí |

> Para este escenario: **multithreaded + auto-replace nodos** → Memcached gana.

---

### Por qué las otras opciones fallan

| Opción | Por qué falla |
|---|---|
| **Redis Global Datastore** | Redis no es multithreaded. No detecta/reemplaza nodos automáticamente. Global Datastore es para replicación cross-region, no para este caso |
| **RDS + RDS Proxy** | Base de datos relacional → latencia en milisegundos, no sub-ms. Costoso para almacenamiento de sesiones |
| **ELB Sticky Sessions** | Enruta usuarios al mismo servidor (no comparte sesiones). Si ese servidor falla → sesión perdida. No es distribuido |

---

### Regla mental para el examen

> - **Sesiones distribuidas + multithreaded + auto-replace nodos** → **ElastiCache Memcached + Auto Discovery**
> - **Persistencia + estructuras complejas + pub/sub** → **ElastiCache Redis**
> - **Sticky sessions** → NO comparte estado, solo fija el usuario a un servidor
> - **RDS para sesiones** → funcional pero costoso y lento comparado con caché en memoria
   
&nbsp;   

&nbsp;   

&nbsp;

## CloudFront Origin Groups: Alta Disponibilidad con Failover

### ¿Qué es un Origin Group en CloudFront?

```
Origin Group
├── Origen Primario  → recibe tráfico normal
└── Origen Secundario → CloudFront cambia automáticamente
                        si el primario falla o devuelve
                        códigos HTTP de error específicos

Requisito: mínimo DOS orígenes para configurar origin failover
```

---

### La solución correcta

```
AZ-A                    AZ-B
┌──────────┐           ┌──────────┐
│ EC2 #1   │           │ EC2 #2   │
│(primario)│           │(secundario)│
└──────────┘           └──────────┘
      └───────────────────┘
              ↑
        Origin Group
              ↑
         CloudFront
         (distribución global)
```

Si EC2 #1 (AZ-A) falla → CloudFront automáticamente usa EC2 #2 (AZ-B) ✅

---

### Por qué las otras opciones fallan

| Opción | Error específico |
|---|---|
| **S3 para contenido dinámico** | S3 solo sirve **contenido estático**. El contenido dinámico requiere EC2 u otro servidor de aplicaciones |
| **Auto Scaling Group como origen** | No puedes usar un ASG directamente como origen en CloudFront. Además necesitas **al menos 2 orígenes** para origin failover |
| **Lambda@Edge en origin group** | Lambda@Edge no puede configurarse como parte de un origin group en CloudFront |

---

### Regla mental para el examen

> - **Alta disponibilidad en CloudFront** → **Origin Group con 2+ orígenes en diferentes AZs**
> - **Origen primario falla** → CloudFront automáticamente usa el **origen secundario**
> - **S3 como origen** → solo para contenido estático
> - **EC2 como origen** → para contenido dinámico
> - Origin failover requiere **mínimo 2 orígenes** configurados en el grupo
   
&nbsp;   

&nbsp;   

&nbsp;

## Fault Tolerance Multi-AZ: Cálculo del Número Óptimo de Instancias

### La fórmula clave

```
Requisito: mínimo N instancias funcionando INCLUSO si una AZ falla
Número de AZs: Z

Instancias por AZ = N / (Z - 1)

→ N=6, Z=3: 6 / (3-1) = 6/2 = 3 instancias por AZ
```

---

### Verificación de la solución correcta

```
3 instancias en eu-west-1a
3 instancias en eu-west-1b
3 instancias en eu-west-1c
Total: 9 instancias

Si eu-west-1a falla:
eu-west-1b (3) + eu-west-1c (3) = 6 instancias ✅ mínimo cumplido
```

---

### Análisis de todas las opciones

| Distribución | Total | Si una AZ falla | ¿Cumple? | Costo |
|---|---|---|---|---|
| 2+2+2 | 6 | 4 instancias | ❌ (necesita 6) | Más barato pero inválido |
| **3+3+3** | **9** | **6 instancias** | **✅** | **Óptimo** |
| 6+6+0 | 12 | 6 instancias | ✅ | Más costoso que 3+3+3 |
| 6+6+6 | 18 | 12 instancias | ✅ | Más costoso, over-provisioned |

---

### Fault Tolerance vs High Availability

```
High Availability                Fault Tolerance
─────────────────                ───────────────
Al menos 1 instancia             Mínimo N instancias
funcionando                      funcionando siempre
Sin degradación de servicio      Sin degradación de servicio
requerida necesariamente         requerida ← más estricto
```

---

### Regla mental para el examen

> Para fault tolerance con pérdida de **1 AZ** entre **Z AZs**:
> **Instancias por AZ = Mínimo requerido ÷ (Z - 1)**
>
> Ejemplo: 6 instancias mínimas, 3 AZs → 6÷2 = **3 por AZ** (9 total)
   
&nbsp;   

&nbsp;   

&nbsp;

## Lambda@Edge + Kinesis: Procesamiento de Streaming en Tiempo Real

### Los dos requisitos técnicos del escenario

```
1. Procesar datos CERCA del usuario (baja latencia geográfica)
   → Lambda@Edge (ejecuta en edge locations de CloudFront)

2. Procesar datos de STREAMING en tiempo real (clickstream)
   → Amazon Kinesis (no Athena, no Route 53)
```

---

### La arquitectura correcta

```
Usuarios globales
      ↓
CloudFront Edge Location (más cercana al usuario)
      ↓
Lambda@Edge ← ejecuta lógica en la ubicación del edge ✅
      ↓
Amazon Kinesis ← procesa streaming en tiempo real ✅
      ↓
Amazon S3 ← almacenamiento durable de resultados ✅
```

---

### Por qué las otras opciones fallan

| Opción | Error específico |
|---|---|
| **CloudFront + Lambda@Edge + Amazon Athena** | Athena es un servicio de **consultas SQL sobre datos en S3** (análisis batch). No procesa streaming en tiempo real |
| **CloudFront + Route 53 latency + Kinesis** | Route 53 solo **enruta tráfico DNS**, no tiene capacidad de cómputo. No puede procesar datos cerca del usuario |
| **CloudFront + Route 53 Geoproximity + Kinesis** | Mismo problema: Route 53 es solo routing, sin capacidad de procesamiento |

---

### Distinción clave: Route 53 vs Lambda@Edge

```
Route 53                         Lambda@Edge
────────                         ──────────
Solo DNS routing                 Ejecuta código en edge locations
Decide A DÓNDE va el tráfico     PROCESA el tráfico en el edge
Sin capacidad de cómputo         Función Lambda completa
No reduce latencia de proceso    Latencia mínima (cercano al usuario)
```

---

### Regla mental para el examen

> - **Procesar datos cerca del usuario + baja latencia** → **Lambda@Edge**
> - **Streaming en tiempo real (clickstream, logs)** → **Amazon Kinesis**
> - **Consultas SQL sobre datos históricos en S3** → **Amazon Athena**
> - **Route 53** → solo enrutamiento DNS, nunca procesamiento de datos
   
&nbsp;   

&nbsp;   

&nbsp;

## AWS Control Tower: Gobernanza Multi-Cuenta con Mínimo Esfuerzo

### Los requisitos del escenario

```
1. Crear múltiples cuentas AWS dentro de una Organización
2. Configuraciones preaprobadas por el equipo de seguridad
3. Estandarizar baselines y configuraciones de red
4. Mínimo esfuerzo de implementación
```

---

### La solución: AWS Control Tower Landing Zone

```
AWS Control Tower
├── Landing Zone → entorno multi-cuenta bien arquitectado
├── Account Factory → crea cuentas con configuraciones preaprobadas ✅
├── Guardrails → políticas de gobernanza pre-empaquetadas
│   ├── Preventivos (SCPs) → bloquean recursos no conformes
│   └── Detectivos (AWS Config) → detectan no-conformidad
└── Automatiza: CloudFormation + SCPs + AWS Config rules
```

**Tres formas de crear cuentas en Control Tower:**
```
1. Account Factory console (AWS Service Catalog)
2. Enroll account feature
3. Lambda + IAM roles (programático)
```

---

### Por qué las otras opciones fallan

| Opción | Por qué es incorrecta |
|---|---|
| **AWS RAM** | Comparte **recursos existentes** entre cuentas. No crea cuentas nuevas ni estandariza configuraciones |
| **AWS Config aggregator + conformance packs** | Config agrega datos de cumplimiento pero **no provisiona cuentas**. Los conformance packs son solo colecciones de reglas Config |
| **Systems Manager OpsCenter + Security Hub** | OpsCenter gestiona **items operacionales** (tickets). No crea cuentas. Security Hub detecta hallazgos de seguridad, no estandariza configuraciones |

---

### Mapa de servicios de gobernanza AWS

```
Crear y gobernar múltiples cuentas    → AWS Control Tower
Políticas a nivel de organización     → AWS Organizations (SCPs)
Detectar no-cumplimiento de recursos  → AWS Config
Compartir recursos entre cuentas      → AWS Resource Access Manager
Hallazgos de seguridad centralizados  → AWS Security Hub
Gestionar operaciones/incidentes      → Systems Manager OpsCenter
```

---

### Regla mental para el examen

> - **Crear cuentas con configuraciones estandarizadas + guardrails** → **AWS Control Tower**
> - **Control Tower = Landing Zone + Account Factory + Guardrails**
> - **AWS Config** → audita/detecta, no provisiona cuentas
> - **AWS RAM** → comparte recursos, no crea cuentas
> - Cuando el escenario menciona "múltiples cuentas + gobernanza + mínimo esfuerzo" → **Control Tower**
   
&nbsp;   

&nbsp;   

&nbsp;


## Respuesta: Spot Instances

Dos señales clave en el escenario indican Spot:

```
Señal 1: "Solo necesarias hasta reducir el backlog"
→ Uso temporal, no permanente

Señal 2: "Si el proceso se interrumpe, otro instance lo retoma"
→ La aplicación tolera interrupciones ← característica clave para Spot
```

---

### Comparación de tipos de instancia

| Tipo | Costo | Interrupción | Ideal para |
|---|---|---|---|
| **Spot** | Hasta 90% menos que On-Demand | Posible (2 min aviso) | Cargas tolerantes a fallos ✅ |
| **On-Demand** | Precio estándar | No | Cargas variables sin compromiso |
| **Reserved** | Descuento por contrato 1-3 años | No | Cargas predecibles y permanentes |
| **Dedicated** | El más caro | No | Requisitos de compliance/licencias |

---

### Regla mental para el examen

> - **Temporal + tolerante a interrupciones + costo-efectivo** → **Spot Instances**
> - Si el escenario menciona que la app puede **recuperarse de fallos** → Spot es la respuesta
> - **Backlog temporal** = no necesitas Reserved (compromiso largo plazo)
   
&nbsp;   

&nbsp;   

&nbsp;

## Amazon Managed Prometheus + Managed Grafana: Monitoreo de Contenedores

### Los requisitos del escenario

```
1. Usar las mismas herramientas (Prometheus + Grafana)
2. Monitorear cargas en EC2+Docker, ECS, y EKS
3. Solución recomendada (mínimo overhead de gestión)
```

---

### La solución correcta y sus roles

```
Contenedores (EC2, ECS, EKS)
         ↓ métricas
Amazon Managed Service for Prometheus
├── Recolecta métricas de contenedores ✅
├── Compatible con modelo de datos Prometheus (PromQL)
├── Serverless, sin gestionar infraestructura
└── Workspace = fuente de datos
         ↓ data source
Amazon Managed Grafana
├── Visualización y dashboards ✅
├── Alertas
└── Consultas sobre datos de Prometheus
```

> **Flujo correcto:** Prometheus recolecta → Grafana visualiza (no al revés)

---

### Por qué las otras opciones fallan

| Opción | Error específico |
|---|---|
| **Grafana como fuente de datos en Prometheus** | **Roles invertidos**: Prometheus recolecta métricas, Grafana las visualiza usando Prometheus como data source |
| **ECS cluster con Prometheus+Grafana en contenedores** | Posible pero requiere gestionar el cluster manualmente. Los servicios managed son la recomendación |
| **VM Import/Export → EC2 con Prometheus+Grafana** | Mucho trabajo manual + debes gestionar el EC2. No es la recomendación para entornos cloud |

---

### Servicios Managed vs Self-managed

```
Self-managed (en EC2 o ECS)      AWS Managed Services
───────────────────────          ────────────────────
Tú gestionas el servidor         AWS gestiona la infraestructura
Tú escalas manualmente           Escala automáticamente
Tú aplicas parches               Sin parches que gestionar
Mayor overhead operacional       Mínimo overhead ✅
```

---

### Regla mental para el examen

> - **Prometheus + Grafana en AWS sin gestionar infraestructura** → **Amazon Managed Service for Prometheus + Amazon Managed Grafana**
> - **Prometheus** → recolecta métricas (es la fuente de datos)
> - **Grafana** → visualiza datos usando Prometheus como data source
> - Soporta: EC2+Docker, ECS, EKS (en EC2 y Fargate), entornos híbridos
   
&nbsp;   

&nbsp;   

&nbsp;

## SQS + ApproximateNumberOfMessages: Evitar Pérdida de Requests

### El problema del escenario

```
Problema actual:
Requests llegan → EC2 intenta procesarlas → sobrecarga
Auto Scaling lanza nuevas EC2 → pero ya se perdieron requests ❌

La causa raíz: no hay buffer entre los requests y el procesamiento
```

---

### La solución: SQS como buffer + scaling por métrica

```
Requests entrantes
      ↓
SQS Queue (buffer durable) ← requests NO se pierden ✅
      ↓
EC2 instances pollan la cola
      ↓
CloudWatch monitorea: ApproximateNumberOfMessages
      ↓
Auto Scaling ajusta instancias según backlog ✅
```

**Cálculo del backlog por instancia:**
```
Backlog per instance = ApproximateNumberOfMessages / instancias activas

Ejemplo:
├── 1,500 mensajes en cola / 10 instancias = 150 msg/instancia
├── Latencia aceptable: 10s / tiempo proceso: 0.1s = 100 msg/instancia (target)
└── 150 > 100 → Auto Scaling agrega 5 instancias más
```

---

### Por qué las otras opciones fallan

| Opción | Por qué no resuelve el problema |
|---|---|
| **Cluster Placement Group** | Mejora latencia entre nodos, pero no evita pérdida de requests. Además reemplaza Auto Scaling, que sí se necesita |
| **Instancias más grandes + EFA** | Instancias más grandes no previenen pérdida en spikes grandes. EFA es para comunicación inter-nodos HPC, no para este caso |
| **Aurora Serverless + Parallel Query** | Aurora Serverless escala la **base de datos**, no las instancias EC2. Parallel Query es para consultas analíticas |

---

### Regla mental para el examen

> - **Requests perdidos por sobrecarga** → **SQS como buffer** (decoupling)
> - **Escalar EC2 basado en cola SQS** → métrica **ApproximateNumberOfMessages**
> - SQS garantiza que los mensajes **no se pierdan** aunque las instancias estén ocupadas
> - **EFA** → HPC/comunicación inter-nodos, no para request buffering
> - **Aurora Serverless** → escala DB, nunca EC2
   
&nbsp;   

&nbsp;   

&nbsp;


## Respuesta: AWS Storage Gateway → S3 Glacier Deep Archive

**Decisión 1: ¿Qué servicio para la transición desde tape backup?**
```
Organización usa tape backup on-premises
         ↓
AWS Storage Gateway (Tape Gateway)
├── Reemplaza cintas físicas por cintas virtuales en AWS
├── Compatible con aplicaciones de backup existentes ✅
├── Sin cambiar workflows actuales
└── Cifra y comprime datos automáticamente
```

**Decisión 2: ¿Qué clase de storage para 10 años + acceso 1-2 veces/año?**
```
S3 Glacier Flexible Retrieval    S3 Glacier Deep Archive
──────────────────────────       ───────────────────────
Retención largo plazo            Retención muy largo plazo ✅
Acceso en minutos/horas          Acceso en horas (12-48h)
Más costoso                      Hasta 75% más barato ✅
                                 Ideal para 10 años ✅
```

---

### Por qué las otras opciones fallan

| Opción | Error |
|---|---|
| **Storage Gateway → Glacier Flexible Retrieval** | Válido pero más costoso que Deep Archive |
| **Snowball Edge → Glacier Flexible Retrieval** | Snowball no integra directamente con Glacier. Además Flexible Retrieval es más caro |
| **S3 + lifecycle → Glacier Flexible Retrieval** | Difícil integrar tape backup directamente con S3 sin Storage Gateway. Además Flexible Retrieval no es el más costo-efectivo |

---

### Regla mental para el examen

> - **Tape backup on-premises → AWS** → **Storage Gateway (Tape Gateway)**
> - **Archivado 10+ años + mínimo costo** → **S3 Glacier Deep Archive**
> - Acceso ocasional (1-2 veces/año) tolera tiempo de recuperación de horas → Deep Archive es suficiente
   


&nbsp;   

&nbsp;   

&nbsp;

## Respuesta: AWS CloudTrail

```
AWS CloudTrail registra:
├── Todas las llamadas API a recursos AWS ✅
├── Acciones via consola, SDK, CLI y servicios AWS
├── Quién hizo qué, cuándo y desde dónde
└── Datos para auditoría y compliance ✅
```

---

### Por qué los otros servicios no aplican

| Servicio | Propósito real |
|---|---|
| **Amazon CloudWatch** | Monitorea **métricas y logs** de rendimiento. No rastrea API calls específicas |
| **AWS X-Ray** | **Debugging y tracing** de microservicios. No audita API calls de infraestructura |
| **Redshift Spectrum** | **Feature de Redshift** para consultar datos en S3. No es un servicio de monitoreo |
| **AWS CloudTrail** | ✅ Registra toda la actividad API en tu cuenta AWS |

---

### Regla mental para el examen

> - **Auditoría de API calls + compliance** → **AWS CloudTrail**
> - **Métricas de rendimiento + alarmas** → **Amazon CloudWatch**
> - **Debugging de microservicios + tracing** → **AWS X-Ray**
   
&nbsp;   

&nbsp;   

&nbsp;


## Respuesta: AWS Application Migration Service (MGN)

```
Rehosting (lift-and-shift) de servidores físicos completos:
├── Aplicaciones
├── Datos
└── Sistemas operativos
         ↓
AWS MGN
├── Replica servidores on-premises → AWS automáticamente
├── Convierte y lanza servidores en AWS cuando estés listo
├── Mínima interrupción al negocio ✅
└── Funciona con servidores físicos y virtuales
```

---

### Por qué las otras opciones no aplican

| Servicio | Propósito real | ¿Aplica aquí? |
|---|---|---|
| **AWS DMS** | Migración de **bases de datos** solamente | ❌ No migra apps ni OS |
| **AWS Snowball** | Transferencia física de **datos** en volumen | ❌ No replica aplicaciones en ejecución |
| **AWS DataSync** | Transferencia/sincronización de **datos** | ❌ No replica apps ni OS. Replicación horaria causa interrupción |
| **AWS MGN** | **Lift-and-shift completo** (apps + datos + OS) | ✅ |

---

### Regla mental para el examen

> - **Rehost completo (apps + OS + datos)** → **AWS MGN**
> - **Solo base de datos** → **AWS DMS**
> - **Solo datos/archivos** → **AWS DataSync o Snowball**
> - **Snowball** → volúmenes masivos sin conexión de red suficiente
   
&nbsp;   

&nbsp;   

&nbsp;

### Aurora Replicas: Mejorando la Disponibilidad de la Base de Datos

**¿Por qué Aurora Replicas?**

```
Aurora Replicas:
├── Comparten el mismo volumen de almacenamiento que el primario
├── Actualizaciones del primario visibles inmediatamente en réplicas
├── En caso de fallo del primario → réplica puede promoverse automáticamente
└── También mejoran rendimiento de lecturas (bonus)
```

---

### Por qué las otras opciones fallan

| Opción | Por qué es incorrecta |
|---|---|
| **Auto Scaling groups + ELB para Aurora** | Aurora es un servicio **managed** de RDS. No se despliega en EC2 instances manuales |
| **Hash Joins** | Optimización de **performance de queries** con equijoins. No mejora disponibilidad |
| **Asynchronous Key Prefetch** | Mejora **performance de queries** con joins entre índices. No mejora disponibilidad |

---

### Nota importante del examen

> La solución **óptima** para disponibilidad en Aurora sería **Multi-AZ**, pero como no estaba disponible en las opciones, **Aurora Replicas** es la siguiente mejor opción ya que pueden **promoverse a primario** automáticamente en caso de fallo.

---

### Regla mental para el examen

> - **Alta disponibilidad Aurora** → **Multi-AZ** (primero) o **Aurora Replicas** (segundo)
> - **Escalar lecturas** → **Aurora Replicas**
> - **Hash Joins / Key Prefetch** → siempre relacionados con **performance de queries**, nunca con disponibilidad
   


&nbsp;   

&nbsp;   

&nbsp;

### Escalando Kinesis Data Streams: Aumentar Shards con UpdateShardCount

**¿Por qué aumentar el número de shards?**

Cada shard en Kinesis tiene una capacidad fija:
```
Por shard:
├── Entrada: 1 MB/s o 1,000 registros/s
└── Salida: 2 MB/s

Si el data rate supera la capacidad → performance degradada ❌
Solución: más shards = más capacidad ✅
```

**El comando correcto:**
```
UpdateShardCount → aumenta shards (shard split)
MergeShard      → reduce shards (dos shards → uno)
```

---

### Por qué las otras opciones fallan

| Opción | Por qué es incorrecta |
|---|---|
| **MergeShard** | **Reduce** capacidad al combinar shards → empeora el problema |
| **Reemplazar con Data Firehose** | Firehose no tiene mayor throughput que Kinesis Streams. Streams escala sin límite añadiendo shards |
| **Step Scaling** | Step Scaling es una política de **Auto Scaling para EC2**. No existe en Kinesis Data Streams |

---

### Regla mental para el examen

> - **Performance degradada en Kinesis por alto data rate** → **aumentar shards con UpdateShardCount**
> - **Reducir costos en Kinesis con bajo tráfico** → **MergeShard** (menos shards)
> - Kinesis cobra **por shard**, más shards = más costo pero más capacidad
> - **Step Scaling** → exclusivo de EC2 Auto Scaling, no aplica a Kinesis
   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;
   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;


   
&nbsp;   

&nbsp;   

&nbsp;