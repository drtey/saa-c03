# AWS SAA-C03 — Cheatsheet de Patrones de Pregunta

> Basado en preguntas reales de examen. Cada entrada = patrón de escenario → servicio correcto + distractores frecuentes.
> Actualizar con `/update cheatsheet` cuando se añadan nuevas preguntas a review_tests.md.

---

# ÍNDICE RÁPIDO DE SEÑALES

| Señal en el enunciado | Servicio / Solución |
|---|---|
| "too many connections" + Lambda + RDS | RDS Proxy |
| "burst within seconds" + API | API Gateway + Lambda |
| "malicious URLs" + "blacklisted FQDNs" | AWS Network Firewall |
| "prevent deletion or overwriting" + migrate | DataSync + S3 + Object Lock |
| "master keys never sent to AWS" + "unencrypted data never sent to AWS" | Client-side encryption + client-side master key |
| "memory", "swap", "disk utilization" en EC2 | CloudWatch Agent |
| "track configuration changes" + "compliance" | AWS Config |
| "SOC", "PCI", "ISO" compliance reports | AWS Artifact |
| "shared file system" + "POSIX-compliant" + multi-EC2 | Amazon EFS |
| "iSCSI" + Windows + Multi-AZ | FSx for NetApp ONTAP |
| "burst" + "tráfico predecible por horario" | Scheduled Scaling |
| "User-Agent" + "custom headers" + edge | Lambda@Edge |
| "decoupled" + on-premises + EC2 | SQS + SWF |
| "SSO" + "directorio corporativo" + multi-cuenta | IAM Identity Center + Organizations |
| "AD corporativo" + AWS | AD Connector |
| "Compartir Transit GW / subnets entre cuentas" | AWS RAM |
| "IP estática / whitelist" + load balancer | EIP + NLB (ALB no acepta EIP) |
| "automated backup" + EBS + simple | Amazon DLM |
| "Kubernetes serverless" | EKS + Fargate |
| "Docker sin Kubernetes" | ECS + Fargate |
| "relaciones" + "grafo" + "recomendaciones" | Amazon Neptune |
| "IoT" + "métricas en tiempo real" | Amazon Timestream |
| "big data" + Spark/Hadoop | Amazon EMR |
| "streaming" + múltiples consumers | Kinesis Data Streams |
| "cola de mensajes" + desacoplamiento | SQS |
| "fan-out" + múltiples suscriptores | SNS → SQS queues |
| "AMQP" / "JMS" / migración legacy MQ | Amazon MQ |
| "ETL" + conversión de formato | AWS Glue |
| "ETL trigger inmediato" al subir a S3 | EventBridge + Glue |
| "SQL ad-hoc" sobre S3 | Amazon Athena |
| "SFTP administrado" + S3/EFS | AWS Transfer Family |
| "migración masiva física" (PB) | Snowball / Snowmobile |
| "migración servidores completos (lift-and-shift)" | AWS MGN |
| "migración solo DB" | AWS DMS |
| "cambiar motor de DB" | AWS SCT + DMS |
| "datos históricos" on-prem → AWS | AWS DataSync → S3 Glacier Deep Archive |
| "acceso híbrido continuo" con caché local | AWS Storage Gateway |
| "tape backup" on-prem → AWS | Storage Gateway (Tape Gateway) |
| "guardrails" + "nuevas cuentas estandarizadas" | AWS Control Tower |
| "consolidar múltiples cuentas" | AWS Organizations |
| "DDoS volumétrico" | AWS Shield Advanced |
| "SQL injection / XSS" + ALB/CloudFront | AWS WAF |
| "WAF en múltiples cuentas" | AWS Firewall Manager |
| "PII en S3" + clasificación automática | Amazon Macie |
| "vulnerabilidades en EC2/containers" | Amazon Inspector |
| "detección de amenazas sin configurar" | Amazon GuardDuty |
| "rotación automática de secretos" | AWS Secrets Manager |
| "auditoría de API calls" | AWS CloudTrail |
| "métricas + alarmas + notificaciones" | CloudWatch + SNS |
| "notificaciones email de sistema" (no marketing) | SNS (no SES) |
| "reportes compliance AWS (SOC/PCI/ISO)" | AWS Artifact |
| "RDS sin espacio + menor overhead" | RDS Storage Auto Scaling |
| "múltiples dominios distintos + HTTPS + sin reprovisioning" | ALB + SNI (múltiples certificados) |
| "contenido privado S3 + solo via CloudFront" | OAC + CloudFront Signed URLs/Cookies |
| "ETL reprocessa datos antiguos" | AWS Glue Job Bookmark |
| "encrypted config variables + cost-effective" | SSM Parameter Store SecureString |
| "encrypted config variables + rotación automática" | AWS Secrets Manager |
| "real-time analytics + read records in batches" | Kinesis Data Streams + Lambda |
| "prevent modification + multiple AWS accounts" | SCP en OU (Organizations) |
| "EC2 no accesible desde Internet" | IP pública + route table con IGW |
| "Provisioned Aurora → Serverless + mínimo downtime" | AWS DMS |
| "MFA obligatorio + departments + single account" | IAM Group + IAM Policy con condición MFA |

---

# DOMINIO 1: Design Resilient Architectures

---

## Alta Disponibilidad y Fault Tolerance

### ASG Multi-AZ — Cálculo de Instancias
**Patrón:** "Mínimo N instancias SIEMPRE funcionando, incluso si una AZ falla"
```
Fórmula: min_asg = N × número_de_AZs
Ejemplo: mínimo 2 siempre → min=4 con 2 AZs (2 por AZ)
```
- **Trampa:** min=2 con 1 por AZ → si una AZ falla queda 1 instancia (ASG tarda en lanzar)
- **Regla:** El min del ASG debe sobrevivir el fallo de una AZ SIN esperar autoscaling

### RDS Multi-AZ vs Read Replica
| | Multi-AZ | Read Replica |
|--|----------|-------------|
| Replicación | **Síncrona** | Asíncrona |
| Acceso en caliente | No (standby) | Sí (lectura) |
| Failover | **Automático** | Manual (promoción) |
| Propósito | HA | Escalar lecturas |

- **"Alta disponibilidad / failover automático"** → **Multi-AZ**
- **"Escalar lecturas"** → **Read Replicas** (nunca Multi-AZ)
- RDS restore = **siempre nueva instancia** (nueva dirección, no in-place)

### Aurora Global Database
- RPO < 1 segundo, RTO < 1 minuto, multi-región
- **"RPO/RTO estricto + relacional + multi-región"** → Aurora Global Database
- **"NoSQL multi-región"** → DynamoDB Global Tables

### Aurora Provisioned → Serverless
- **No se puede cambiar de clase de instancia** de Provisioned a Serverless — requiere nuevo cluster
- **Mínimo downtime** en migración → **AWS DMS** (source sigue activo durante la migración)
- Snapshot restore = downtime completo; Failover a replica = breve indisponibilidad de escrituras

### NAT Gateway — Eliminar SPOF
- **1 NAT GW por AZ en subnet pública** — cada AZ independiente
- Route table de instancias privadas → NAT GW de su propia AZ
- Más de 1 NAT GW por AZ = innecesario

---

## Escalado

### Políticas de Auto Scaling
| Política | Cuándo usarla |
|---|---|
| **Target Tracking** | Mantener métrica en valor objetivo (CPU 50%) — más sencilla |
| **Step Scaling** | Ajustes proporcionales al tamaño del breach ("set of scaling adjustments") |
| **Scheduled Scaling** | Tráfico predecible por horario → escala ANTES del pico |
| **Predictive Scaling** | ASG homogéneo (mismo tipo instancia) — ML predice tráfico |

- **"Tráfico lento al inicio del día"** + horario fijo → **Scheduled** (no Dynamic, llega tarde)
- **Predictive Scaling falla** con mezcla de instance types/sizes (necesita ASG homogéneo)
- Dynamic scaling es **reactivo** — siempre tarde ante picos conocidos

### Kinesis — Problemas de Performance
- Alto data rate → **aumentar shards** (`UpdateShardCount`)
- Bajo tráfico → **MergeShard** (reduce coste)
- Kinesis cobra por shard. **Step Scaling** → NO aplica a Kinesis (es de EC2 ASG)

---

## Almacenamiento Resiliente

### EBS — Hechos Clave para el Examen
- Replicado dentro de la **misma AZ** (no cross-AZ, no cross-region)
- Adjuntar: solo instancias en la **misma AZ**
- Multi-Attach: solo **io1/io2** en instancias Nitro de la misma AZ
- Snapshots → **S3** (no RDS, no EFS)
- Cambios en vivo sin downtime: tipo, tamaño, IOPS
- SLA: **99.999%**

### EFS — Cuándo Usar
- **File storage compartido + multi-AZ + múltiples EC2 + POSIX** → EFS
- Linux únicamente (NFS v4)
- **S3** = object storage, no POSIX, no file locking → no sirve para CMS/file system

### FSx — Decisión Rápida
| Necesidad | Servicio |
|---|---|
| Windows + SMB + Active Directory | FSx for Windows File Server |
| Block storage + iSCSI + Multi-AZ (Windows) | **FSx for NetApp ONTAP** |
| HPC + Linux + POSIX + alta performance | FSx for Lustre |

- **"iSCSI"** en el enunciado → señal directa a **NetApp ONTAP**

### S3 — Object Lock y Backup
- **Object Lock (WORM)** = solo S3 — ni EFS, ni EBS
- **Amazon DLM** = snapshots EBS automatizados, sin coste extra, sin scripts
- **AWS Backup** = multi-servicio (más overhead que DLM para solo EBS)
- DataSync puede escribir **directamente** en Glacier Deep Archive (sin S3 Standard + lifecycle)

### RDS Storage Auto Scaling
- **RDS sin espacio + menor overhead** → **Storage Auto Scaling** (no manual resize)
- **Provisioned IOPS** = mejora velocidad/rendimiento, **no aumenta espacio**
- Storage Auto Scaling = zero downtime + automático + sin coste adicional
- `Increase allocated storage` = manual, requiere intervención cada vez → más overhead

---

## Mensajería y Eventos

### S3 Notifications — Fan-out Pattern
```
S3 → solo 1 destino. Para múltiples consumers:
S3 → SNS Topic → SQS Queue A
              → SQS Queue B
```
- SNS es **push** (entrega activa). SQS es **pull** (polling)
- SQS no hace polling a SNS — SQS se **suscribe** al SNS Topic

### SQS FIFO vs Standard
- **Mensajes duplicados** → **FIFO Queue** (exactly-once delivery)
- **Orden crítico** → FIFO
- **Máximo throughput** sin importar duplicados → Standard
- **Visibility timeout** → evita que otros vean el mensaje, NO elimina duplicados

### SQS como Buffer — Patrón Anti-Pérdida
- Requests se pierden por sobrecarga → **SQS como buffer**
- Escalar EC2 basado en cola → métrica **`ApproximateNumberOfMessages`**

---

## Route 53

### Routing Policies — Cuándo Usar Cada Una
| Policy | Caso de uso |
|---|---|
| **Failover** | Active-Passive: primary + standby |
| **Weighted** | Distribuir tráfico en % (canary, migración) |
| **Latency** | Menor latencia al cliente (no es más cercano geográficamente) |
| **Geolocation** | País/continente específico, sin ajuste de cobertura |
| **Geoproximity + bias** | Controlar tamaño del área geográfica → bias + expande, bias - reduce |
| **Multi-Value** | Hasta 8 records con health check, devuelve solo los sanos |

- **"Enrutar mayor porción desde una zona geográfica"** → **Geoproximity + bias**
- **Active-Active** (todos disponibles siempre) → Weighted/Latency/Geolocation con health checks
- **Active-Passive** (primary + backup) → **Failover routing policy**

---

## CloudFront

### Origin Groups — Failover
- **Alta disponibilidad en CloudFront** → Origin Group con 2+ orígenes
- Primary falla → CloudFront usa automáticamente el origen secundario

### Lambda@Edge
- Ejecuta código en edge locations: Node.js o Python
- 4 puntos de interceptación: Viewer Request, Origin Request, Origin Response, Viewer Response
- **"User-Agent"** / **"custom headers"** / **"A/B testing"** / **"personalización en edge"** → Lambda@Edge
- **CloudFront response headers policy** = headers estáticos, NO lógica dinámica
- Lambda@Edge **no soporta VPC ni Layers**

### VPC — Accesibilidad desde Internet (Troubleshooting)
Cuando un EC2 no es accesible desde Internet, verificar **DOS cosas**:
1. **¿Tiene IP pública (Public IP o Elastic IP)?**
2. **¿La route table tiene ruta `0.0.0.0/0 → IGW`?**

- **Customer Gateway (CGW)** = componente VPN (lado cliente on-premises) — no para tráfico Internet
- **EFA** = rendimiento HPC — no necesario para acceso a Internet
- **Auto Scaling Group** = escalado de capacidad — no afecta routing ni IPs
- Nueva subnet = NO hereda auto-assign public IP ni route table con IGW → configurar manualmente

---

# DOMINIO 2: Design High-Performing Architectures

---

## Compute

### Lambda — Cuándo y Cuándo No
- **"Burst de tráfico en segundos"** → **API Gateway + Lambda** (escala en segundos)
- EC2/ECS/Beanstalk Auto Scaling escala en **minutos** (no segundos)
- **"Too many connections" + Lambda + RDS** → **RDS Proxy** (connection pooling)
- Aumentar concurrency de Lambda sin RDS Proxy **empeora** el error de conexiones

### ECS vs EKS vs Fargate
| Caso | Solución |
|---|---|
| Docker sin Kubernetes | ECS + Fargate |
| Kubernetes serverless | EKS + Fargate |
| Kubernetes con autoscaling | EKS + Kubernetes Cluster Autoscaler |
| Lambda con dependencias complejas | Lambda con Container Image Support (hasta 10 GB /tmp) |

- **ECS** = Docker; **EKS** = Kubernetes. ECS no puede "correr un cluster Kubernetes"
- **EKS Anywhere / ECS Anywhere** = infraestructura del cliente on-premises, no AWS managed

### Tipos de Instancia EC2 — Señales Rápidas
| Señal | Familia |
|---|---|
| "High sequential read/write + large datasets + local storage" | Storage Optimized (I, D, H) |
| "Fast processing IN MEMORY" | Memory Optimized (R, X, z) |
| "Compute-bound + batch" | Compute Optimized (C) |
| "Balance compute/memory/networking" | General Purpose (M, T) |
| "HPC + inter-node communications + OS bypass" | EFA (Elastic Fabric Adapter) |

---

## Bases de Datos

### DynamoDB — Diseño y Performance
- **Schema flexible + cambios frecuentes + alto tráfico** → DynamoDB
- **Partition key de alta cardinalidad** = mejor distribución de I/O (evita hot partitions)
- **GSI** = eventually consistent, crear en cualquier momento
- **LSI** = strong consistency, solo al crear la tabla
- **DAX** = microsegundos, write-through, no requiere cambios de código (misma API)

### DynamoDB — Auto Scaling y CLI
- **Auto Scaling habilitado por defecto** en tablas creadas por **Consola** ✅
- **Auto Scaling NO habilitado por defecto** en tablas creadas por **AWS CLI** ❌ — hay que activarlo manualmente
- **CloudFront + DynamoDB** → **INCOMPATIBLES** (CloudFront no puede usar DynamoDB como origin)
- **DAX** = mejora lecturas milisegundos → microsegundos (hasta 10x)

### RDS — Monitorización
| Qué monitorizar | Herramienta |
|---|---|
| Procesos/threads individuales del SO | **Enhanced Monitoring** (agente en la instancia) |
| Métricas generales de la instancia | CloudWatch |
| Queries lentas / rendimiento SQL | **RDS Performance Insights** |
| Cambios de datos (INSERT/UPDATE) | Aurora Native Functions → Lambda |
| Eventos de infraestructura (failover, backup) | RDS Event Subscriptions |

### Memoria y Swap en EC2
- **Memoria, swap, uso de disco** = **NO en CloudWatch por defecto**
- Requieren **CloudWatch Agent** instalado en la instancia
- **Detailed monitoring** = solo aumenta frecuencia (5min → 1min), no añade nuevas métricas

### RDS Proxy
- **"Too many connections"** + arquitectura serverless → **RDS Proxy**
- Mantiene connection pool → Lambda reutiliza conexiones existentes
- Aumentar concurrencia Lambda sin proxy = peor

---

## Almacenamiento y Transferencia

### Patrones de Transferencia de Datos
| Caso | Solución |
|---|---|
| Migración one-time on-prem → AWS | AWS DataSync |
| Acceso híbrido continuo con caché local | AWS Storage Gateway |
| Migración masiva física (TB-PB) | Snowball / Snowball Edge |
| SFTP administrado hacia S3/EFS | AWS Transfer Family |
| Transferencia rápida global a S3 | Transfer Acceleration + Multipart Upload |
| Tape backup on-prem → Glacier | Storage Gateway (Tape Gateway) |

- **DataSync → Glacier Deep Archive** directamente (sin S3 Standard + esperar 30 días)
- **Storage Gateway** = on-premises sigue activo; **DataSync** = on-premises se abandona

### S3 Lifecycle — Reglas Clave
- Standard → Standard-IA: mínimo **30 días**
- Standard-IA → Glacier: mínimo **30 días** adicionales
- **EFS lifecycle**: solo transiciona a IA, **nunca elimina** objetos
- EFS lifecycle máximo: 365 días → no sirve para retención >1 año

---

## API y Arquitectura

### API Gateway — Throttling y Caché
- **Picos de tráfico → proteger backend** → Throttling + Caching en API Gateway
- **Canary Release** = mínima disrupción + cost-effective en API Gateway
- **Blue-Green** = más costoso (dos entornos completos)
- Errores 4XX = cliente (429 = throttling), 5XX = servidor (504 = timeout backend)

### Desacoplamiento
- **"Decoupled architecture" + on-premises + EC2** → SQS + SWF
- **SWF** = coordinación de workflows distribuidos (menos conocido, distractor frecuente)
- VPC Peering = solo entre VPCs AWS, **nunca con on-premises**
- RDS/DynamoDB = bases de datos, **nunca** son la respuesta para "desacoplar"

### Kinesis — Real-Time Analytics
| | **Kinesis Data Streams (KDS)** | **Kinesis Data Firehose** |
|---|---|---|
| Latencia | **Milisegundos** (real-time) | ~60 segundos (near real-time) |
| Lambda como consumer | ✅ Lee en batches | ⚠️ Solo transformación, no consumer |
| Destinos | Consumidores personalizados | S3, Redshift, OpenSearch, Splunk |
| Retención | 24h - 365 días | No retiene (entrega directa) |

- **"Real-time" + "read records in batches"** → **KDS + Lambda**
- **Firehose**: Lambda = transformador, no consumer final
- **Athena / Redshift Spectrum** = análisis histórico en S3, **no real-time**

### AWS Glue — Job Bookmark
- **ETL reprocessa datos antiguos** → **Habilitar Job Bookmark**
- Job Bookmark: rastrea último punto procesado → próximas ejecuciones solo procesan datos nuevos
- Parallelizar con EC2 = acelera pero sigue reprocesando datos antiguos (no resuelve causa raíz)
- Lambda + EventBridge para borrar datos = frágil (pierde datos si el job falla)

---

## Networking

### Load Balancers — Decisión Rápida
| Necesidad | LB |
|---|---|
| HTTP/HTTPS, routing por contenido (Layer 7) | ALB |
| UDP / Layer 4 / IP estática / whitelist | **NLB** |
| IP estática en Load Balancer | EIP → solo NLB (ALB no acepta EIP) |
| NLB delante de ALB | Patrón válido para EIP + funcionalidad Layer 7 |
| Múltiples dominios HTTPS sin reprovisionar | **ALB + SNI** (múltiples certs en mismo listener) |

### ALB + SNI — Múltiples Dominios HTTPS
- **SNI (Server Name Indication)**: permite múltiples dominios en la misma IP — incluye hostname en el TLS handshake
- ALB selecciona automáticamente el certificado correcto para cada cliente
- **Sin coste adicional** — incluido en el precio del ALB
- **Wildcard certificate** = solo subdominios (`*.dominio.com`) — no dominios distintos
- **SAN certificate** = válido pero requiere **reprovisionar** al añadir un nuevo dominio
- **CloudFront + dedicated IPs** = cargo mensual adicional → no cost-effective

### Transit Gateway vs VPC Peering
- **Cientos de VPCs + VPNs + multi-región** → **AWS Transit Gateway**
- VPC Peering = no transitivo, solo dos VPCs, sin on-premises
- VPN CloudHub = solo VPNs, no VPCs

---

# DOMINIO 3: Design Secure Architectures

---

## Cifrado y Claves

### S3 Encryption — Comparativa
| Método | Datos a AWS | Master Key a AWS | Quién cifra |
|---|---|---|---|
| **Client-side + client master key** | Cifrados ✅ | ❌ Nunca | Cliente |
| **Client-side + KMS key** | Cifrados ✅ | KeyId sí | Cliente |
| **SSE-KMS** | En claro ❌ | Gestionada AWS ❌ | AWS (S3) |
| **SSE-C** | En claro ❌ | Enviada en request ❌ | AWS (S3) |

- **"Nunca enviar master key NI datos en claro a AWS"** → **client-side + client-side master key**
- SSE-C: AWS recibe la clave y cifra en su lado (datos llegan en claro)

### KMS — Puntos Clave
- Keys **nunca salen de KMS** en texto plano
- KMS cifra hasta **4KB** directo; datos mayores → DEK (Data Encryption Key)
- **Control total + eliminar key material** → KMS Custom Key Store + CloudHSM
- **CloudHSM** = FIPS 140-2 Level 3 (vs KMS Level 2)

---

## IAM y Acceso

### Decisión de Acceso
| Caso | Solución |
|---|---|
| Servicio AWS accede a otro | IAM Role (nunca access keys hardcodeadas) |
| AD corporativo + AWS (on-premises) | AD Connector + IAM Roles |
| SSO multi-cuenta + directorio corporativo | IAM Identity Center |
| App móvil/web accede a AWS | Cognito Identity Pool + Role |
| 1200+ usuarios en AD | Federation + STS (no IAM Users individuales) |
| Cross-account access | Role en cuenta destino + trust policy |

- **IAM Identity Center** = SSO entre cuentas con directorio corporativo
- **Cognito** = apps/usuarios externos (social login, web/mobile) — NO para empleados con AD
- **Organizations NO tiene "external authentication"** → usar IAM Identity Center
- **SCP no otorgan permisos**, solo limitan. Management account NO afectada por SCPs

### IAM Groups + MFA Policy (single account)
- **Múltiples usuarios por departamento + MFA obligatorio + cuenta única** → **IAM Group + IAM Policy con condición MFA**
- **IAM Group** recibe **IAM Policies** — no Roles directamente
- **IAM Role → IAM User** no es asignación directa — el user asume el role (assume role)
- **SCP** aplica solo a Organizations (root/OU/cuenta) — **nunca a IAM Users directamente**
- **Permissions boundary** = define máximo de permisos, no es herramienta de autenticación

### Almacenamiento de Secrets y Config
| Caso | Servicio |
|---|---|
| Config variables, DB hostnames, env settings (estáticos) | **SSM Parameter Store SecureString** (gratis) |
| Credenciales que necesitan rotación automática | **AWS Secrets Manager** (~$0.40/secreto/mes) |

- **Parameter Store SecureString** = cifrado con KMS, sin coste en Standard tier
- **Secrets Manager** = costoso para valores estáticos — se justifica solo con rotación automática
- **SSM OpsCenter** = gestión de incidentes operacionales (OpsItems) — **no un datastore de config**

### S3 — Seguridad
- **Presigned URLs** = acceso temporal. Generadas con Role → expiran con las credenciales del role
- **MFA Delete** = solo activable por root via CLI
- **Block Public Access** = override de todas las políticas públicas
- **Object Lock Compliance** = ni root puede borrar hasta que expire

---

## CloudFront — Contenido Privado

### OAC + Signed URLs/Cookies
**Patrón:** Solo clientes específicos acceden a archivos en S3, únicamente vía CloudFront

```
Cliente → CloudFront (con Signed URL/Cookie) → S3 (solo accesible por OAC)
```

| Mecanismo | Propósito |
|---|---|
| **OAC (Origin Access Control)** | Bloquea acceso directo a S3 — solo CloudFront puede leer |
| **Signed URL** | Acceso temporal a **un archivo** específico — un usuario concreto |
| **Signed Cookie** | Acceso temporal a **múltiples archivos** — un usuario concreto |
| **CloudFront Functions** | JS ligero para transformaciones (URL rewrites, headers) — NO control de acceso |
| **Origin Shield** | Capa adicional de caché (rendimiento) — NO es seguridad |

- **OAC** = reemplaza OAI (Origin Access Identity) — más moderno, soporta SSE-KMS
- **S3 Presigned URLs** = acceso temporal directo a S3, no escala bien, no pasa por CloudFront

---

## Servicios de Seguridad — Mapa

```
Ataques web (SQL injection, XSS)          → AWS WAF
WAF en múltiples cuentas                  → AWS Firewall Manager
DDoS volumétrico (L3/L4)                  → AWS Shield Advanced
Filtrar FQDNs / URLs maliciosas en VPC    → AWS Network Firewall
Detección de amenazas (sin configurar)    → Amazon GuardDuty
PII / datos sensibles en S3               → Amazon Macie
Vulnerabilidades EC2/containers/Lambda    → Amazon Inspector
Postura de seguridad centralizada         → AWS Security Hub
Reportes compliance AWS (SOC/PCI/ISO)     → AWS Artifact
Auditoría de API calls                    → AWS CloudTrail
Configuraciones de recursos + compliance  → AWS Config
Secretos + rotación automática            → AWS Secrets Manager
```

### DDoS Mitigation — Qué NO sirve
- **Dedicated EC2 instances** = solo opción de facturación/hardware, no mitiga DDoS
- **EFA (Elastic Fabric Adapter)** = aceleración HPC/ML; **máximo 1 por instancia**; no mitiga DDoS
- Técnicas válidas: Shield, WAF, CloudFront, ALB + Auto Scaling, RDS en subnet privada

### Distractor Frecuente — Seguridad
- **GuardDuty**: detecta amenazas, **nunca bloquea** directamente
- **CloudTrail**: audita acciones (quién hizo qué), NO estados de configuración
- **AWS Config**: audita estados (cómo está configurado), NO acciones — **solo detecta, no previene**
- **Network Firewall NO se integra directamente con ALB** — se integra a nivel VPC via endpoints
- **NAT Gateway** = salida a internet para recursos privados, **no filtra** FQDNs ni URLs

---

## Multi-Cuenta y Gobernanza

### Decisión de Servicio
| Necesidad | Servicio |
|---|---|
| Consolidar múltiples cuentas | AWS Organizations |
| SSO con directorio corporativo | IAM Identity Center |
| Compartir recursos entre cuentas (Transit GW, subnets, License Manager) | AWS RAM |
| Crear cuentas estandarizadas con guardrails | AWS Control Tower |
| Políticas a nivel organización | SCPs (Organizations) |
| Detectar no-cumplimiento de recursos | AWS Config |
| Logging centralizado multi-cuenta | CloudTrail + CloudWatch Logs |
| **Evitar que usuarios modifiquen recursos en sus cuentas** | **SCP en OU** |

### SCPs — Comportamiento Clave
- **SCP puede restringir al root user** de cada cuenta miembro — las IAM Policies NO pueden
- SCP se adjunta a **root / OU / cuenta** en Organizations — **nunca a IAM Users o Roles directamente**
- SCP no otorga permisos — solo limita el máximo disponible
- **Management account** = NO está afectada por SCPs propios

- **Control Tower = Landing Zone + Account Factory + Guardrails**
- **AWS Config** no provisiona cuentas — solo audita configuraciones
- **RAM** comparte recursos existentes, no crea cuentas
- Para unir cuentas existentes: crear org en master → invitar child accounts
- AD corporativo on-premises → IAM Identity Center via **AD Connector**

---

## Network Security

### VPC — Firewall y Filtrado
- **Filtrar URLs maliciosas + FQDNs** → **AWS Network Firewall** (Suricata-compatible, stateful)
- **Defense-in-depth**: ALB en público, EC2 en privado, DB en privado más restrictivo
- **IPv6 solo salida** → **Egress-Only Internet Gateway**
- **IPv4 solo salida** (instancias privadas) → **NAT Gateway**

### NACL vs Security Groups — Stateless vs Stateful
| | **Security Group** | **NACL** |
|---|---|---|
| Estado | **Stateful** (retorno automático) | **Stateless** (requiere regla explícita de retorno) |
| Regla inbound 443 | Solo necesitas la inbound | Necesitas inbound 443 + outbound puertos efímeros |
| Puertos efímeros outbound | Automático | 32768-65535 (Amazon Linux) / 49152-65535 (Windows 2008+) |

- **NACL bloqueando todo + permitir HTTPS** → regla inbound TCP 443 + regla outbound 32768-65535
- **Customer Gateway (CGW)** = componente VPN — no Internet Gateway

### Bastion Host
- Siempre en **subnet pública** con **Elastic IP**
- Windows → RDP (TCP 3389), Linux → SSH (TCP 22)
- Acceso solo desde IPs corporativas conocidas (no 0.0.0.0/0)

---

# DOMINIO 4: Design Cost-Optimized Architectures

---

## Compute Cost

### Spot Instances
- **"Temporal + tolerante a interrupciones + reducir backlog"** → **Spot Instances**
- App puede recuperarse de fallos → Spot es la respuesta
- EMR task nodes = ideales para Spot (sin HDFS, sin riesgo de pérdida de datos)

### Reserved Instances
- **RI no usadas** (app desmantelada) → terminar instancias + vender en **RI Marketplace**
- RI Marketplace = solo Standard RIs (no Convertible)
- Instancia detenida no = sin cargos → EIPs y RI siguen cobrando
- RI expirada sin terminar la instancia → sigue en On-Demand

### EC2 Billing — Trampas
- `stopping → stop` = **no** se cobra
- `stopping → hibernate` = **sí** se cobra
- `pending`, `stopped`, `shutting-down` = no se cobra (On-Demand/Spot)

---

## Storage Cost

### S3 — Clases y Lifecycle
| Clase | Señal en el enunciado |
|---|---|
| Standard-IA | Acceso < 1x/mes, no archivado |
| Glacier Flexible | Archivado largo plazo, recuperación en minutos/horas |
| Glacier Deep Archive | Archivado 7-10 años, acceso rarísimo (horas), más barato |
| Intelligent-Tiering | Patrón de acceso desconocido o variable |

- **DataSync → Glacier Deep Archive** directamente (más barato que S3 Standard + lifecycle 30d)
- **EFS lifecycle** solo transiciona a IA, no elimina

### EBS vs Instance Store
- **EBS** persiste en stop. **Instance Store** se pierde en stop/fallo de hardware
- Instance Store: mayor performance (>260,000 IOPS), ephemeral, solo al lanzar

---

## Database Cost

### DynamoDB Cost
- **On-Demand** = tráfico impredecible. Más caro en carga sostenida alta
- **Provisioned + Auto Scaling** = más barato para carga predecible
- **TTL** = expira items sin consumir WCU (borrado asíncrono, hasta 48h)
- **Imágenes/archivos grandes** → siempre en **S3**, referencia/metadata en DynamoDB

### Aurora Serverless
- Para cargas variables/intermitentes → Aurora Serverless v2
- Escala a casi 0 cuando no hay actividad

---

## Arquitecturas Cost-Effective

### Patrones Comunes
| Escenario | Solución |
|---|---|
| API + tráfico variable | API Gateway + Lambda (pay-per-request) |
| DB en EC2 con overhead | Migrar a DynamoDB/RDS (managed service) |
| Backlog temporal + tolerante a interrupción | Spot Fleet |
| File sharing on-prem + caché local | Storage Gateway File Gateway |

---

# TRAMPAS FRECUENTES DEL EXAMEN

---

## Distractores por Categoría

### Networking
- **VPC Peering** = no transitivo, no sirve con on-premises
- **Global Accelerator** = multi-región; una sola región → no aplica
- **EIP** = solo en **NLB**, no en ALB
- **NAT GW** = no filtra tráfico, no inspecciona FQDNs
- **Customer Gateway (CGW)** = VPN — no para conectividad Internet (usar IGW)
- **NACL stateless** = siempre configurar inbound + outbound (puertos efímeros) explícitamente

### Bases de Datos
- **RDS Multi-AZ** = HA, **no escala lecturas**
- **RDS restore** = siempre nueva instancia (nueva dirección)
- **DynamoDB GSI** = solo eventually consistent
- **DAX** = mejora lecturas, no escrituras
- **DMS puede migrar a DynamoDB** (origen relacional o MongoDB)
- **Aurora Provisioned → Serverless** = NO es cambio de clase de instancia — necesita DMS
- **DynamoDB Auto Scaling con CLI** = NO habilitado por defecto (sí con Consola)
- **CloudFront + DynamoDB** = INCOMPATIBLES como origin

### Monitorización
- **CloudTrail** = API calls (quién hizo qué), no métricas de rendimiento
- **Config** = estado de configuraciones, no auditoría de acciones
- **Detailed monitoring** = frecuencia 5min→1min, no nuevas métricas
- **Memoria/swap** = NO en CloudWatch por defecto → necesitan CloudWatch Agent

### Seguridad
- **GuardDuty** = detecta, nunca bloquea
- **Cognito** = apps externas/usuarios web, no AD corporativo
- **SCP** = limitan pero no otorgan permisos; management account no afectada
- **SCP** = NUNCA se adjunta a IAM Users directamente — solo a root/OU/cuenta
- **CloudTrail** ≠ compliance reports → usar **AWS Artifact**
- **SSE-C** = AWS recibe la clave (datos llegan en claro)
- **Network Firewall** no se integra con ALB directamente
- **AWS Config** = detecta incumplimientos, **no los previene** — usar SCP para prevenir
- **IAM Policies** no aplican a root user de la cuenta — solo **SCP** puede restringir al root
- **Wildcard cert** = subdominios únicamente; **SAN** = múltiples dominios pero requiere reprovisionar
- **Origin Shield** = rendimiento/caché — no es una función de seguridad
- **CloudFront Functions** = JS ligero (headers, redirects) — no control de acceso
- **Secrets Manager** (~$0.40/secreto/mes) = costoso para config estática → usar SSM Parameter Store
- **SSM OpsCenter** = incidentes operacionales — no datastore de configuración

### Escalado
- **Predictive Scaling** = requiere ASG homogéneo (falla con mixed instance types)
- **Scheduled Scaling** = escala ANTES del pico conocido
- **Dynamic scaling** = reactivo, llega tarde a picos predecibles
- **Aumentar concurrency Lambda** + DB sin RDS Proxy = **empeora** "too many connections"
- **RDS Storage Auto Scaling** = espacio; **Provisioned IOPS** = velocidad (no aumenta espacio)

### Almacenamiento
- **Storage Gateway** = on-premises sigue activo; DataSync = migración one-time
- **EBS** = replicado en la misma AZ (no cross-AZ, no cross-region)
- **EFS** = no tiene Object Lock; Object Lock = **solo S3**
- **Snapshots EBS** → van a **S3**, no RDS
- **DLM** = EBS solo; **AWS Backup** = multi-servicio (más overhead)

### Servicios Confundidos
| Confusión frecuente | Realidad |
|---|---|
| SES para alertas de sistema | SES = marketing/transaccional; **SNS** = sistema/ops |
| RAM para crear cuentas | RAM comparte recursos, no crea cuentas |
| Config para provisionar cuentas | Config audita configuraciones, no provisiona |
| ParallelCluster para multi-cuenta | ParallelCluster = HPC clusters, no gestión de cuentas |
| Control Tower para compartir recursos | Control Tower = gobernanza; **RAM** = compartir recursos |
| Firewall Manager = firewall | Firewall Manager = administración centralizada de WAF/Shield |
| Inspector para compliance reports | Inspector = vulnerabilidades; **Artifact** = compliance docs |
| SWF = cola de mensajes | SWF = coordinación de workflows distribuidos |
| EFA para request buffering | EFA = HPC inter-node; **SQS** = buffering |
| ECS para correr Kubernetes | ECS = Docker; **EKS** = Kubernetes |
| Dedicated EC2 para DDoS | Dedicated = facturación; EFA = HPC — ninguno mitiga DDoS |
| Firehose + Lambda como consumer | Lambda con Firehose = transformación; **KDS** = consumer con Lambda |
| Athena para real-time | Athena = histórico en S3; **KDS** = real-time |
| Job Bookmark = paralelismo | Job Bookmark = evitar reprocesar datos; paralelismo = velocidad |

---

# PATRONES COMBINADOS FRECUENTES

---

## Patrones de Arquitectura

```
Serverless API con picos:
  API Gateway → Lambda → RDS (con RDS Proxy si muchas conexiones)

Fan-out a múltiples consumers:
  S3 Event → SNS Topic → SQS Queue A + SQS Queue B

Streaming en tiempo real + almacenamiento:
  Kinesis Data Streams → Lambda (transformar) → DynamoDB/S3

ETL automático al subir archivo:
  S3 PUT → EventBridge → AWS Glue Job → S3 (Parquet)

Reaccionar a cambios en DynamoDB:
  DynamoDB Streams → Lambda → SNS (notificar múltiples subs)

Reaccionar a cambios en Aurora MySQL:
  Aurora MySQL → Native Functions (lambda_sync/lambda_async) → Lambda

Multi-cuenta con SSO:
  AWS Organizations + IAM Identity Center + AD Connector (on-prem AD)

Defense-in-depth 3 capas:
  Internet → ALB (público) → EC2 ASG (privado) → Aurora (privado)
  + AWS Network Firewall (filtrar FQDNs/URLs maliciosas)

Backup automatizado EBS:
  Amazon DLM (simple, sin coste) o AWS Backup (multi-servicio)

Migración datos históricos:
  DataSync → S3 Glacier Deep Archive (directo, sin pasar por Standard)

IP fija en load balancer:
  EIP → NLB → (opcional: NLB delante de ALB para Layer 7)

Contenido privado S3 via CloudFront:
  S3 + OAC (bloquea URLs directas) + Signed URLs/Cookies (autoriza usuarios)

ETL sin reprocesar datos anteriores:
  AWS Glue + Job Bookmark habilitado

Multi-dominios HTTPS sin reprovisionar:
  ALB + múltiples certificados SSL + SNI (automático, sin coste)

Restringir acciones en cuentas AWS (multi-cuenta):
  Organizations + OU + SCP (incluso bloquea root user)
```

---

## Señales de Restricción → Implicación

| Restricción en el enunciado | Implicación |
|---|---|
| "Mínimo cambio en el código / aplicación" | Elastic Beanstalk, DMS, Amazon MQ, DAX |
| "Sin gestionar servidores / mínimo overhead" | Lambda, Fargate, Aurora Serverless, DynamoDB |
| "Más económico para carga variable" | Spot / On-Demand / Serverless sobre Reserved |
| "Mayor rendimiento de red dedicado" | Direct Connect > VPN |
| "Acceso temporal a S3 para usuario externo" | Presigned URL |
| "Credenciales para servicio AWS → otro" | IAM Role (nunca access keys hardcodeadas) |
| "Escalar lecturas en DB" | Read Replicas, no Multi-AZ |
| "Datos no borrables / compliance" | Object Lock Compliance / Vault Lock |
| "Cifrado con control total de keys" | KMS CMK o CloudHSM |
| "Datos sensibles en S3 / PII" | Amazon Macie |
| "Detectar amenazas sin configurar logs" | GuardDuty |
| "Workflow multi-paso > 15 min" | Step Functions |
| "Múltiples cuentas + governance centralizada" | Organizations + Control Tower |
| "Compartir recursos entre cuentas" | AWS RAM |
| "Directorio corporativo + SSO + multi-cuenta" | IAM Identity Center + AD Connector |
| "Burst en segundos + API" | API Gateway + Lambda |
| "Tráfico predecible por horario" | Scheduled Scaling |
| "Tráfico lento al inicio del día" | Scheduled Scaling (no Dynamic) |
| "Too many connections + serverless" | RDS Proxy |
| "IP estática / whitelist en LB" | EIP + NLB |
| "FQDNs maliciosos / URLs maliciosas" | AWS Network Firewall |
| "Nunca enviar keys ni datos a AWS" | Client-side encryption + client master key |
| "POSIX + shared + multi-EC2" | Amazon EFS |
| "iSCSI + Windows + Multi-AZ" | FSx for NetApp ONTAP |
| "RDS sin espacio + least operational overhead" | RDS Storage Auto Scaling |
| "Prevent modification en cuentas hijas" | SCP en OU |
| "Múltiples dominios HTTPS + no reprovisionar" | ALB + SNI |
| "Solo via CloudFront + cliente específico" | OAC + Signed URLs/Cookies |
| "ETL reprocessa datos viejos" | AWS Glue Job Bookmark |
| "Encrypted config variables + cost-effective" | SSM Parameter Store SecureString |
| "Rotación automática + credentials" | AWS Secrets Manager |
| "Real-time analytics + batches" | Kinesis Data Streams + Lambda |
| "EC2 no accesible desde Internet" | Verificar IP pública + route table → IGW |
