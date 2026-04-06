# AWS SAA-C03 — Cheatsheet por Dominios del Examen

> Organizado por los 4 dominios oficiales del examen (SA-Associate).
> Cada sección cubre los puntos más testados, comparativas clave y trampas comunes.

---

# DOMINIO 1: Design Resilient Architectures

---

## Conceptos Base — HA, FT y DR

- **HA (High Availability)** = minimizar tiempo de inactividad. Pequeña disrupción es aceptable (ej. re-login durante failover). Ejemplo: Multi-AZ RDS hace failover en 60-120s
- **Fault Tolerance (FT)** = el sistema opera a través del fallo sin ninguna interrupción. Más costoso y complejo que HA. Ejemplo: sistemas de aviónica, transacciones financieras en tiempo real
- **Disaster Recovery (DR)** = recuperación tras un evento catastrófico cuando HA/FT han fallado
  - **RPO** (Recovery Point Objective) = cuánta pérdida de datos es aceptable (tiempo desde el último backup válido)
  - **RTO** (Recovery Time Objective) = cuánto tiempo puede estar el sistema caído hasta recuperar operación normal

### Estrategias de DR (menor → mayor coste/complejidad)
| Estrategia | RTO/RPO | Descripción |
|-----------|---------|-------------|
| Backup & Restore | Horas | Snapshots periódicos a S3. Restaurar desde cero al desastre |
| Pilot Light | Minutos | Solo el core mínimo corriendo (ej. DB replicando). Escalar el resto al activar |
| Warm Standby | Segundos-Minutos | Versión reducida del sistema activa en otra región. Escalar al failover |
| Multi-Site Active-Active | Segundos o menos | Múltiples sitios activos simultáneamente. Máximo coste |

---

## EC2 — Resiliencia y Ciclo de Vida

- **EC2 es AZ resilient** — si falla la AZ, falla la instancia. Para HA: distribuir en múltiples AZs con un ELB
- **Stop & Start** migra la instancia a otro host EC2 dentro del mismo AZ → se pierde la IP pública dinámica (pero no la Elastic IP). Instance Store se **pierde**
- **Terminate** = elimina la instancia. EBS con "delete on termination" activado se elimina
- **Termination Protection** = flag que impide terminación accidental. Útil para role separation (junior admin no puede terminar si está activado)
- **Instance Status Checks**: System status (hardware/red AWS) + Instance status (OS/filesystem). CloudWatch puede auto-recuperar instancias ante fallos de sistema
- **AMI = regional.** Deben copiarse explícitamente entre regiones. Los snapshots EBS subyacentes se copian con ella
- **AMI Baking** = crear AMI con app preinstalada y configurada. Más rápido al lanzar vs bootstrapping puro con User Data

### Placement Groups
| Tipo | Distribución | Resiliencia | Caso de uso |
|------|-------------|-------------|-------------|
| **Cluster** | Mismo rack, misma AZ | Muy baja | HPC, ML, baja latencia (<10Gbps stream) |
| **Spread** | Racks distintos, AZs distintas | Alta | Instancias críticas individuales (máx 7/AZ) |
| **Partition** | Grupos en racks físicos aislados | Media-Alta | Hadoop, Cassandra, Kafka (tolerancia a fallo de rack) |

---

## EBS — Resiliencia y Snapshots

- **EBS = AZ resilient** (replicado dentro de la AZ). Para mover entre AZs: Snapshot → crear volumen en otra AZ
- **EBS persiste** cuando la instancia se detiene (Stop). Solo se pierde si se termina con "delete on termination" activo
- **Snapshots** son incrementales y se almacenan en S3 (gestionado por AWS → region resilient). Primera snapshot = copia completa de los datos usados (no del tamaño total del volumen)
- **FSR (Fast Snapshot Restore)** = restauración con rendimiento completo inmediato, sin lazy loading. Hasta 50 snapshots por región. Coste adicional
- **EBS Encryption** = cifrado transparente al OS (sin pérdida de rendimiento). DEK único por volumen. Snapshots y volúmenes derivados heredan el mismo DEK. **No se puede descifrar un volumen cifrado**
- Billing de snapshots: por GB de **datos usados** (no el tamaño del volumen)

---

## RDS — Alta Disponibilidad

- **Multi-AZ** = réplica síncrona en otra AZ del mismo VPC. Failover automático via cambio de CNAME DNS en **60-120 segundos**
  - La standby **NO se puede usar para lecturas ni consultas** — solo es un hot standby para HA
  - Backups automáticos se toman de la standby (elimina impacto en performance de la primaria)
  - Triggers de failover: fallo de AZ, fallo de instancia, mantenimiento programado, cambio de instance type, software patching
  - **Sin free tier.** Coste = 2x instancia single-AZ
  - **Read Replicas** = replicación **asíncrona**. Accesibles para consultas de lectura. Hasta **5 por instancia primaria**
  - Pueden estar en la misma región o cross-region. Cross-region = resiliencia global
  - **RPO ≈ 0**. Se pueden promover a primaria en caso de fallo (**bajo RTO pero irreversible** — la réplica deja de ser réplica)
  - **Escalan lecturas, NO escrituras**. Para escalar escrituras → Aurora Multi-Master o sharding

### Multi-AZ vs Read Replica — Diferencia clave
| | Multi-AZ | Read Replica |
|--|----------|-------------|
| Replicación | Síncrona | Asíncrona |
| Propósito | Solo HA | Performance (lecturas) + HA (promoción) |
| Regiones | Misma región | Misma o diferente región |
| Acceso en caliente | No (standby) | Sí (lectura) |
| Failover | Automático (60-120s) | Manual (promoción) |

- **Backups automáticos** = 0-35 días de retención. PITR disponible con logs de transacciones cada 5 min. Restaurar siempre crea **una nueva instancia RDS** (nueva dirección)
- **Snapshots manuales** = no expiran aunque se borre el RDS. También restauran como nueva instancia

---

## Aurora — Arquitectura Resiliente

- **Cluster Volume compartido** replicado en **3 AZs × 2 copias = 6 copias**. Sin almacenamiento local por nodo
- Puede perder hasta **2 copias** sin perder escrituras, hasta **3 copias** sin perder lecturas. Reparación de datos automática
- Hasta **15 réplicas de lectura** (vs 5 en RDS). Failover mucho más rápido que RDS Multi-AZ (segundos)
- **Endpoints:** Cluster (escritura al primario), Reader (load balancing entre réplicas), Custom (subconjunto definido de instancias)
- **Aurora Serverless v2** = escala en fracciones de ACU, incluso a capacidad casi 0. Para cargas muy variables o intermitentes
- **Aurora Global Database** = 1 región primaria de escritura + hasta 5 regiones secundarias de lectura. Latencia de replicación < **1 segundo**. **RTO < 1 minuto** para failover a región secundaria
- **Aurora Multi-Master** = múltiples nodos de escritura. Failover de escrituras sin tiempo de inactividad

---

## ELB y Auto Scaling

- **ELB necesita subnets en múltiples AZs** para ser resiliente. Activar **Cross-Zone Load Balancing** para distribuir tráfico igualmente entre instancias en distintas AZs
- **ALB (Application, Layer 7):** HTTP/HTTPS/WebSocket. SSL termina en el ALB. Rules por host-header, path, query-string, source-ip. Targets: instancias, IPs, Lambda, ECS containers
- **NLB (Network, Layer 4):** TCP/UDP/TLS. Ultra-rápido (millones rps). IP estática por AZ (útil para whitelisting). Puede forwarded TLS sin terminarlo (unbroken encryption). Usado con PrivateLink
- **Cuándo NLB sobre ALB:** unbroken SSL, IP estática, no HTTP/S, PrivateLink, máxima performance
- **ASG** = mantiene instancias entre Min/Desired/Max. Auto-reemplaza instancias unhealthy según health checks (EC2 o ELB)
  - **Launch Template** (preferido, soporta versiones y más features) vs Launch Configuration (legacy)
  - **Scaling:** Simple (un threshold), Step (proporcional al breach), Target Tracking (mantiene métrica objetivo), Scheduled, Predictive
  - **Cooldown period** (default 300s) = espera antes de permitir otro scaling action. Evita flapping
  - **Lifecycle Hooks** = pausa el launch/termination para ejecutar acciones custom (registrar en inventory, drenar conexiones, etc.)
  - **Default Termination Policy:** AZ con más instancias → instancia con Launch Configuration más antigua → más próxima al billing hour

---

## Route 53 — Routing Resiliente

- **Health Checks** = separados de los records pero usados por routing policies. Globales, cada 30s (10s = coste extra). Tipos: Endpoint, Calculado (combina HCs con AND/OR), CloudWatch Alarm
- **Failover Routing** = Active-Passive. Primary + Secondary. R53 responde con Secondary solo si Primary es unhealthy. Para DR
- **Active-Active Failover** = usar Weighted o Multi-Value con health checks para que todos los recursos respondan mientras están sanos
- **Multi-Value Routing** = hasta 8 records con mismo nombre, cada uno con health check propio. Solo devuelve los sanos. **No es un Load Balancer** (sin session stickiness ni distribución real de carga)
- **Weighted Routing** = distribución de tráfico en %. Peso 0 = sin tráfico. Para canary deployments y migraciones graduales
- **Latency Routing** = responde desde la región AWS con menor latencia medida al cliente. No es necesariamente la más cercana geográficamente
- **Geolocation** = routing por país/continente del cliente. Para restricciones de contenido, idioma, compliance legal. Más específico gana (país > continente > default). **Necesita un record default** para IPs no mapeadas
- **Geoproximity** = basado en distancia + bias ajustable (+bias expande área de influencia). Solo en Traffic Flow
- **ALIAS** = mapea a recursos AWS (ALB, CF, S3 website, Global Accelerator, etc.). Gratuito para queries. Soporta apex/naked domain. Mismo tipo que el record destino

---

## S3 — Resiliencia y Replicación

- **S3 Standard / Standard-IA / Glacier** = replicados en mínimo **3 AZs**. Durabilidad **99.999999999% (11 nines)**
- **S3 One Zone-IA** = solo 1 AZ. Para datos reproducibles o backups secundarios donde la pérdida es tolerable
- **Versioning** = una vez activado, no se puede desactivar (solo suspender). Cada versión se almacena y factura independientemente. Delete sin Version ID → coloca un **delete marker** (objeto sigue existiendo, reversible)
- **CRR (Cross-Region Replication) / SRR (Same-Region Replication)**:
  - Requiere versioning activado en origen **y** destino
  - No es retroactiva (solo replica objetos nuevos/modificados post-activación)
  - One-way por defecto (origen → destino). No replica deletes por defecto (configurable)
  - No soporta SSE-C. No replica objetos ya en Glacier o Deep Archive
  - **RTC (Replication Time Control)** = garantiza replicación en 15 min. Coste adicional

---

## Conectividad Híbrida y VPN

- **Site-to-Site VPN** = IPSec sobre internet público. Setup en < 1 hora. ~1.25 Gbps. Latencia variable. VGW (AWS) + CGW (on-premises). Para: setup rápido, backup de DX, desarrollo
- **Direct Connect (DX)** = conexión física dedicada (1/10/100 Gbps). Baja latencia consistente. **NO cifra por defecto** (añadir VPN sobre DX para cifrado). Semanas/meses de provisioning. Bajo coste por GB de salida en alto volumen
- **DX + VPN** = cifrado IPSec sobre la conexión DX. Combina performance de DX con seguridad de VPN
- **Transit Gateway (TGW)** = hub central que conecta múltiples VPCs, VPN y DX con **routing transitivo** (diferencia clave vs VPC Peering que no es transitivo). Compartible entre cuentas via AWS RAM

### VPN vs Direct Connect
| | Site-to-Site VPN | Direct Connect |
|--|-----------------|----------------|
| Velocidad | ~1.25 Gbps | 1/10/100 Gbps |
| Latencia | Variable (internet) | Baja y consistente |
| Cifrado | Sí (IPSec) | No (añadir VPN encima) |
| Setup time | < 1 hora | Semanas/meses |
| Coste inicial | Bajo | Alto (port fee) |
| Mejor para | Backup, desarrollo, rápido | Producción, alto volumen, latencia crítica |

---

## Backup y Protección de Datos

- **AWS Backup** = servicio centralizado para backup de EC2, EBS, RDS, Aurora, DynamoDB, EFS, FSx, Storage GW. Backup Plans (frecuencia, retención, lifecycle, copia cross-region), Vaults con KMS
- **Vault Lock (WORM)** = 72h cooloff period post-activación, luego ni AWS puede borrar los backups. Para compliance y regulaciones
- **DynamoDB PITR** = desactivado por defecto. Permite restaurar a cualquier segundo dentro de los últimos **35 días**
- **RDS Automated Backups** = PITR con logs de transacción cada 5 minutos. Ventana configurable 0-35 días
- **EFS Backup** = via AWS Backup o snapshots EFS

---

# DOMINIO 2: Design High-Performing Architectures

---

## EC2 — Performance y Tipos de Instancia

- **General Purpose (M, T):** equilibrio CPU/MEM. Para la mayoría de workloads genéricos
- **Compute Optimized (C):** alta CPU/memoria ratio. Media processing, HPC, gaming servers, ML inference, batch científico
- **Memory Optimized (R, X, z):** alto RAM. In-memory DBs (Redis, SAP HANA), big data en memoria, caching distribuido
- **Storage Optimized (I, D, H):** alta IOPS o throughput local. Bases de datos transaccionales, data warehousing, Elasticsearch, analytics con acceso a datos local
- **Accelerated Computing (P, G, F, Inf):** GPU/FPGA. Deep learning training, graphics rendering, video encoding, HPC con aceleración hardware
- **Decode de tipo:** `R5dn.8xlarge` → R=familia, 5=generación, d=NVMe local storage incluido, n=network enhanced, 8xlarge=tamaño
- **Enhanced Networking (SR-IOV):** mayor throughput, menor latencia, menor CPU overhead. Vía ENA (Elastic Network Adapter, hasta 100 Gbps) o Intel 82599 VF (10 Gbps)
- **ENA (Enhanced Network Adapter)** = driver para enhanced networking. **EFA (Elastic Fabric Adapter)** = ENA + OS-bypass para HPC y ML a escala. No soportado en Windows

---

## EBS — Tipos y Cuándo Usar Cada Uno

| Tipo | IOPS Máx | Throughput Máx | Tamaño | Notas clave |
|------|----------|----------------|--------|-------------|
| **GP3** | 16,000 | 1,000 MiB/s | 1GB-16TB | IOPS/throughput independientes del tamaño. **20% más barato que GP2. Default recomendado** |
| **GP2** | 16,000 | 250 MiB/s | 1GB-16TB | 3 IOPS/GB, burst hasta 3,000. Legacy |
| **io1** | 64,000 | 1,000 MiB/s | 4GB-16TB | 50 IOPS/GB máx. Para DBs críticas |
| **io2** | 64,000 | 1,000 MiB/s | 4GB-16TB | 500 IOPS/GB máx. Mayor durabilidad que io1 |
| **io2 Block Express** | 256,000 | 4,000 MiB/s | 4GB-64TB | Sub-ms latency. Para workloads más exigentes |
| **st1** | 500 (1MB) | 500 MiB/s | 125GB-16TB | Throughput optimizado. **No bootable**. Big Data, logs |
| **sc1** | 250 (1MB) | 250 MiB/s | 125GB-16TB | Cold HDD. **No bootable**. Más barato. Acceso infrecuente |

- **Regla de selección rápida:** Boot/general → GP3. Alta IOPS consistente → io1/io2. Throughput/streaming → st1. Cold/backup → sc1. >260,000 IOPS → Instance Store
- **Instance Store** = almacenamiento físico en el host. Mayor performance que cualquier EBS (D3=4.6GB/s, I3=16GB/s throughput). Ephemeral: se pierde en stop/start, hibernate o fallo de hardware. Solo añadible **al lanzar**
- **RAID 0 + EBS** = suma IOPS y throughput entre volúmenes. Hasta ~260,000 IOPS con io1/io2/GP3

---

## File Systems — EFS vs FSx

**EFS (Elastic File System)**
- NFS v4 para **Linux únicamente** (POSIX permissions). Compartido entre múltiples EC2 en múltiples AZs via mount targets
- Performance modes: **General Purpose** (default, 99.9% casos, menor latencia) | **Max I/O** (miles de clientes, mayor throughput, mayor latencia)
- Throughput modes: **Bursting** (escala con tamaño del filesystem) | **Provisioned** (throughput fijo independiente del tamaño)
- Storage tiers: **Standard** | **Infrequent Access (EFS-IA)** con lifecycle policies automáticas

**FSx for Windows File Server**
- SMB nativo. Integración con Active Directory (AWS DS o self-managed AD). Single o Multi-AZ
- Soporta DFS (Distributed File System), VSS (user-driven restores), Windows permission model (ACLs NTFS)
- Acceso vía VPC, VPN o Direct Connect. Para: entornos Windows, AD integration requerida, aplicaciones legacy Windows

**FSx for Lustre**
- HPC para **Linux** (POSIX). Hasta 100+ GB/s throughput, sub-millisecond latency. ML, Big Data, Financial Modeling
- **Scratch** = máxima performance pura, short-term, **sin replicación, sin HA**. Riesgo de pérdida de datos
- **Persistent** = HA dentro de **1 AZ**, self-healing. Para workloads de producción con duración larga
- Integración nativa con S3: lazy load de S3 al filesystem y export de resultados de vuelta a S3
- Mínimo 1.2TiB, incrementos de 2.4TiB. Scratch: base 200MB/s/TiB. Persistent: 50/100/200 MB/s/TiB

### Regla de decisión
- **Linux multi-instancia compartido** → EFS
- **Windows / AD / SMB** → FSx for Windows
- **HPC / ML / POSIX alta performance** → FSx for Lustre

---

## Bases de Datos — Performance

**ElastiCache**
- **Redis**: Multi-AZ, replicación, backups, estructuras avanzadas (sorted sets, hashes, bitmaps), transacciones, pub/sub. Para: leaderboards, session state con failover, pub/sub, datos con expiry
- **Memcached**: simple key-value, multi-threaded (aprovecha múltiples CPU cores), sharding horizontal, sin replicación ni backup. Para: cache de objetos simples, máxima throughput, sin necesidad de HA
- Requiere **cambios en el código de la aplicación**. Reduce carga en la DB primary para workloads read-heavy
- Patrones: **Cache-aside** (app consulta cache, si miss va a DB), **Write-through** (escribe en cache y DB simultáneamente), **Session store** (instancias stateless guardan sesión en Redis)

**DynamoDB Performance**
- **1 RCU = 1 lectura strongly consistent de 4KB/s** (o 2 lecturas eventually consistent de 4KB/s)
- **1 WCU = 1 escritura de 1KB/s**
- **Provisioned** = RCU/WCU fijos + burst pool de 300 segundos. Más barato para carga predecible
- **On-Demand** = escala automáticamente, paga por millón de R/W. Para tráfico impredecible
- **DAX (DynamoDB Accelerator)** = cluster in-memory en VPC, API-compatible con DynamoDB, latencia en microsegundos. Solo mejora lecturas (write-through). No requiere cambios en código (misma API DynamoDB). No apto para escrituras fuertes ni datos que cambian frecuentemente
- **GSI** = alternate PK y SK, eventually consistent solo, propios RCU/WCU. Crear en cualquier momento. **Default para la mayoría de casos**
- **LSI** = alternate SK sobre el mismo PK, comparte RCU/WCU de la tabla. Crear **solo al crear la tabla**. Usar cuando se necesita **strong consistency** en el índice

**Redshift**
- Data warehouse columnar (OLAP), petabyte scale. SQL vía JDBC/ODBC. **No es OLTP**
- **Una sola AZ** (no Multi-AZ nativo). Leader node (query planning + aggregation) + Compute nodes (ejecución + storage)
- **Redshift Spectrum** = query SQL directo sobre datos en S3 sin necesidad de cargarlos en Redshift
- **Enhanced VPC Routing** = tráfico de Redshift pasa por VPC routing (útil para controlar acceso con endpoints y SGs)
- **Federated Query** = query directo a RDS/Aurora sin ETL

**Amazon Athena**
- Serverless query engine sobre S3. SQL estándar (Presto). **Schema-on-read** (los datos originales no cambian)
- Paga por **TB de datos escaneados**. Optimizar coste: usar Parquet/ORC comprimido, particionamiento
- Ideal para: queries ad-hoc sobre logs (VPC Flow Logs, CloudTrail, ELB), análisis exploratorio, sin ETL, Glue Data Catalog como metastore

---

## Serverless y Mensajería — Performance

**Lambda**
- Memory: 128MB → 10GB. **CPU escala proporcionalmente a la memoria** (no se configura por separado)
- **Cold start** = inicialización del entorno de ejecución + código. Reducir con: Provisioned Concurrency (pre-warm), menor deployment package, código eficiente en init
- **Concurrencia reservada** = límite máximo por función (protege otras funciones de starvation). **Provisioned Concurrency** = instancias pre-inicializadas para eliminar cold starts
- **Timeout máximo: 15 minutos.** Para procesos más largos → Step Functions + Lambda, Batch, ECS/Fargate
- Invocación **síncrona** (API GW, ALB, SDK directo): cliente espera, gestiona errores el cliente
- Invocación **asíncrona** (S3 Events, SNS, EventBridge): Lambda reintenta 2 veces, DLQ para mensajes fallidos tras retries
- **Event Source Mapping** (SQS, Kinesis, DynamoDB Streams): Lambda hace polling y procesa en batches configurables

**Kinesis vs SQS — Cuándo usar cada uno**
| Criterio | Kinesis Data Streams | SQS |
|---------|---------------------|-----|
| Modelo | Rolling window temporal | Queue: delete on consume |
| Consumers | Múltiples simultáneos | 1 grupo de consumers |
| Orden | Por shard (partition key) | FIFO solo en modo FIFO |
| Persistencia | 24h default (hasta 365d) | 4 días default (14 máx) |
| Throughput | Shards (escala manual o on-demand) | Standard: ilimitado. FIFO: 300/3000 TPS |
| Caso de uso | Streaming analytics, múltiples apps leyendo los mismos datos | Desacoplamiento, worker pools, procesamiento one-shot |

**SQS — Puntos Clave**
- **VisibilityTimeout** = tiempo que el mensaje permanece oculto mientras un consumer lo procesa. Si el procesamiento falla (sin delete), el mensaje reaparece para otro consumer. Default: 30s
- **Long Polling** (`WaitTimeSeconds` hasta 20s) = reduce llamadas vacías a la API y coste. Siempre preferible a short polling
- **Dead-Letter Queue (DLQ)** = mensajes que fallan `maxReceiveCount` veces se mueven a DLQ para análisis o re-procesamiento
- **Delay Queue** = período de invisibilidad al entrar a la cola (0-15 min). Diferente a VisibilityTimeout (que empieza al recibir)
- **SNS + SQS Fan-out** = SNS Topic → múltiples SQS queues. Patrón estándar para que múltiples consumers reciban todos los eventos independientemente

**API Gateway**
- Errores **4XX = cliente:** 400 (bad request), 403 (access denied / WAF block), 429 (throttling exceeded)
- Errores **5XX = servidor:** 502 (bad gateway, Lambda retornó output inválido), 503 (service unavailable), 504 (integration timeout, límite 29s)
- **Endpoint types:** Edge-Optimized (CloudFront POP) | Regional (clientes en misma región) | Private (solo VPC via Interface Endpoint)
- **Caching** = TTL default 300s (0-3600s). Reduce latencia y coste de backend

**CloudFront — CDN Performance**
- Edge Locations cachean contenido. Regional Edge Cache = capa intermedia más grande entre edge y origin
- **TTL default: 24 horas.** Control fino: `Cache-Control max-age`, `s-maxage`, `Expires` desde el origin
- Usar **versioned filenames** (v1.jpg → v2.jpg) en lugar de invalidations para mayor control y menor coste
- **Lambda@Edge** = Node.js/Python en edge locations para modificar requests/responses. 4 puntos: Viewer Request, Origin Request, Origin Response, Viewer Response. Sin VPC, sin Layers. Para: A/B testing, auth, personalization
- **ACM Certificados para CloudFront** = **deben estar en us-east-1** (CF es un servicio global que opera como us-east-1)

**Global Accelerator**
- 2 Anycast IPs estáticas globales como entry points. Tráfico entra al edge AWS y transita por backbone privado de AWS
- **No cachea contenido** (diferencia vs CloudFront). Optimiza red para **TCP/UDP de cualquier protocolo**
- Ideal para: gaming/VoIP/IoT (no HTTP/S), IPs estáticas globales, failover multi-región instantáneo (segundos)

---

# DOMINIO 3: Design Secure Architectures

---

## IAM — Identity & Access Management

- **Prioridad de evaluación de políticas:** Explicit DENY > Explicit ALLOW > Default DENY (implícito)
- **IAM es global y gratuito.** Límites: 5,000 usuarios, 300 grupos, usuario en máx 10 grupos. Sin nesting de grupos
- **Managed Policy** = reutilizable, bajo overhead, preferida por defecto. **Inline Policy** = solo para allow/deny excepcional en una identidad específica
- **Grupos NO pueden referenciarse en resource policies** (ej. bucket policy). Solo usuarios, roles o cuentas
- **Roles** = credenciales temporales via **STS (sts:AssumeRole)**. Usar cuando el número de entidades es desconocido, >5000 usuarios, o para servicios AWS
- **Access Keys** = credenciales long-term para CLI/API. Máx 2 por usuario. Solo visibles al crear. Si se pierden, eliminar y recrear. Rotar regularmente
- **ARN** = `arn:aws:s3:::catgifs` (bucket: gestión del bucket) ≠ `arn:aws:s3:::catgifs/*` (objetos dentro del bucket). No son equivalentes
- **Instance Profile** = wrapper que lleva un IAM Role dentro de una instancia EC2. Se crea automáticamente en consola
- **ID Federation** = usuarios externos (AD, SAML 2.0, OIDC) asumen roles IAM → no necesitan cuentas IAM propias
- **Web Identity Federation** = usuarios de apps con Google/Facebook/Cognito asumen roles → acceso a AWS sin credenciales en la app

### Cuándo usar Roles
| Caso | Solución |
|------|---------|
| Servicio AWS accede a otro (Lambda → S3, EC2 → DynamoDB) | IAM Role (nunca access keys hardcodeadas) |
| Corp AD/SAML usuarios acceden a AWS | Federation + Role |
| App móvil accediendo a DynamoDB | Cognito Identity Pool + Role |
| Cross-account access | Role en la cuenta destino, trust policy para la cuenta origen |
| >5000 identidades | Roles + Identity Federation |

---

## AWS Organizations y SCPs

- **SCP** = políticas de permiso que limitan lo que las cuentas pueden hacer (incluso el root de la cuenta)
- **SCPs NO otorgan permisos** — solo limitan. La intersección de SCP + política IAM = acceso efectivo
- **Management account (master) NO está afectada por SCPs** — trampa frecuente en el examen
- **Deny list** (recomendado): FullAWSAccess por defecto + SCPs de DENY específicos (bajo overhead)
- **Allow list**: eliminar FullAWSAccess + crear lista explícita de servicios permitidos (más seguro, más overhead)
- Consolidated billing = descuentos por volumen y reservas compartidas entre cuentas miembro

**Control Tower**
- **Landing Zone** = entorno multi-cuenta bien arquitectado. Security OU (Log Archive + Audit Accounts con CloudTrail & Config)
- **Preventive Guard Rails** = SCP que impiden acciones no conformes
- **Detective Guard Rails** = Config Rules que detectan y alertan sobre drift
- **Account Factory** = aprovisionamiento estandarizado y automatizado de nuevas cuentas (guardrails aplicados automáticamente)

---

## KMS y Cifrado

- **KMS = regional, público, FIPS 140-2 Level 2.** Las keys **nunca salen de KMS** en texto plano
- **KMS Keys** cifran datos de hasta **4KB** directamente. Para datos mayores → **DEK (Data Encryption Key)**
- **Flujo DEK:** KMS genera plaintext DEK + encrypted DEK → plaintext DEK cifra los datos → se descarta el plaintext DEK → se almacenan datos cifrados + encrypted DEK juntos
- **Para descifrar:** enviar encrypted DEK a KMS → KMS devuelve plaintext DEK (si tienes permisos) → descifrar datos → descartar plaintext DEK
- **AWS Managed Keys** = gestionadas por AWS por servicio (aws/s3, aws/ebs). Sin control de rotación ni políticas propias
- **Customer Managed Keys (CMK)** = control total de políticas, rotación, grants. Necesarias para role separation
- **Key Policies** = toda KMS Key tiene una. Sin key policy, nadie (ni root) puede usarla. Se combina con IAM Policies

### Opciones de cifrado en S3
| Método | Gestión de Key | Quién cifra | Role Separation | Cuándo usar |
|--------|---------------|-------------|----------------|-------------|
| **SSE-S3** (AES256) | S3 (AWS) | S3 | No | Default, sin requisitos especiales |
| **SSE-KMS** (aws:kms) | KMS | S3 | **Sí** | Auditoría, control de acceso por key, compliance |
| **SSE-C** | Tú (en cada request) | S3 | - | Cuando debes mantener las keys fuera de AWS |
| **Client-Side** | Tú | Tú | - | Máximo control, cifrado antes de enviar |

**CloudHSM**
- Single-tenant HSM. **FIPS 140-2 Level 3** (vs KMS Level 2). AWS aprovisiona el hardware, tú lo gestionas completamente
- Sin integración nativa con S3 SSE. Usar para: SSL/TLS offload en web servers, Oracle TDE, CA privada, cuando necesitas Level 3 o control total de keys

---

## S3 — Seguridad

- **S3 es privado por defecto** — sin política explícita, todo denegado
- **Bucket Policy** = resource policy. Permite acceso cross-account y a principals anónimos. Tiene campo `Principal`
- **Identity Policy (IAM)** = controla identidades dentro de la misma cuenta. Sin campo `Principal`
- **Block Public Access** = override de todas las políticas públicas. Incluso si una bucket policy permite acceso público, Block Public Access lo niega. Activar siempre salvo en static website hosting
- **ACLs** = legacy, inflexible. Evitar. Solo si el sistema externo no soporta IAM/bucket policies
- **Object Lock (WORM)** = requiere versioning activado:
  - **Compliance Mode**: nadie puede borrar ni modificar, **ni el root**. Inmutable hasta que expire el retention period. Para compliance regulatorio
  - **Governance Mode**: usuarios con `s3:ByPassGovernanceRetention` sí pueden modificar. Para proyectos donde se necesita WORM pero con escape hatch
  - **Legal Hold**: on/off sin periodo de retención. Requiere `s3:PutObjectLegalHold`. Para prevenir borrado durante investigaciones
- **Presigned URLs** = heredan permisos del creador en el momento del acceso. Si el creador pierde acceso, la URL deja de funcionar. **No generar con Roles** (las credenciales temporales del rol expiran antes que la URL)
- **MFA Delete** = requiere MFA para: cambiar estado de versioning o eliminar versiones. Solo activable por root via CLI

---

## VPC — Seguridad y Control de Acceso

**NACL (Network Access Control List)**
- Stateless, nivel subnet. ALLOW + DENY. Solo CIDR (no recursos lógicos como SGs)
- Reglas procesadas en orden numérico ascendente. Primera que hace match gana. `*` = DENY implícito al final
- Requiere reglas explícitas para **ambas direcciones**: request (ej. 443) **y** respuesta (ephemeral ports 1024-65535)
- Default NACL = permite todo. Custom NACL = deniega todo por defecto (solo regla `*` deny)
- 1 subnet = 1 NACL. 1 NACL = múltiples subnets

**Security Groups (SG)**
- Stateful (el response traffic se permite automáticamente), nivel ENI. Solo ALLOW. Soporta referencias a otros SGs y a sí mismo (self-reference)
- **NO explicit DENY** — para bloquear IPs maliciosas específicas necesitas NACL además del SG
- Self-reference = todas las instancias con el mismo SG pueden comunicarse entre sí (útil para clusters)

### NACL vs Security Group
| | NACL | Security Group |
|--|------|----------------|
| Estado | Stateless | Stateful |
| Nivel | Subnet | ENI/Instancia |
| Reglas | ALLOW + DENY | Solo ALLOW |
| Referencias | Solo CIDR | CIDR + SGs + self |
| Orden evaluación | Numérico (primero gana) | Todas se evalúan (OR lógico) |
| Default (custom) | Deny all | Deny all |

**VPC Endpoints**
- **Gateway Endpoint** (S3 y DynamoDB únicamente) = entrada en la route table. Gratis. Regional (no cross-region). Sin ENI
- **Interface Endpoint** (todos los demás servicios AWS) = ENI en subnet específica. Coste por hora + GB. Usa PrivateLink. Para HA: 1 endpoint por AZ. Soporta Private DNS (sobrescribe DNS público del servicio)

**NAT Gateway**
- En subnet pública, usa Elastic IP. AZ resilient dentro de su AZ. Para region resilience: **1 NAT GW por AZ**
- No soporta Security Groups (solo NACLs). **No funciona con IPv6** (usar Egress-Only IGW para IPv6 outbound)
- **VPC Endpoints reemplazan la necesidad de NAT GW** para tráfico a S3/DynamoDB (más barato)

---

## Servicios de Seguridad

**WAF (Web Application Firewall)**
- Layer 7. Protege CloudFront, ALB, API Gateway, AppSync. WebACL = contenedor de rules y rule groups
- Puede filtrar por: IP, país, headers, cookies, URI path, body (primeros 8,192 bytes), método HTTP, query string
- **Rate-based rules** = DDoS L7, limita requests por IP en ventana de tiempo
- Actions: ALLOW, BLOCK (detienen evaluación), COUNT, CAPTCHA (continúan evaluación para multi-stage flows)

**AWS Shield**
- **Standard** = gratis, automático. Protección L3/L4 en el perímetro (R53, CloudFront, Global Accelerator, ELB)
- **Advanced** = $3,000/mes, 1 año de compromiso. L7 (via WAF incluido), Shield Response Team (SRT), cost protection para scaling no mitigado, health-based detection, real-time visibility

**Amazon Macie** = ML para detectar PII, PHI, credenciales, datos financieros en buckets S3. Managed identifiers (AWS) + Custom identifiers (regex propio). Findings a Security Hub y EventBridge

**Amazon Inspector** = escaneo de vulnerabilidades en EC2, containers y Lambda. Network Assessment (sin agente) + Host Assessment (con agente). Findings ordenados por severidad. Reglas: CVEs, CIS benchmarks, network reachability

**Amazon GuardDuty** = threat detection con ML. Analiza CloudTrail Events, VPC Flow Logs, DNS logs. Sin agente, sin configuración previa. Detecta: instancias comprometidas, cuentas con acceso anómalo, cryptomining, exfiltración de datos

**AWS Secrets Manager**
- Para secretos (passwords, API keys, tokens OAuth). **Rotación automática** via Lambda (sin intervención manual)
- Integración nativa con RDS, Redshift, DocumentDB (puede cambiar la contraseña en la DB directamente)
- Si el examen menciona: rotación automática, integración con RDS, secretos → **Secrets Manager** > SSM Parameter Store

**SSM Parameter Store**
- Configs y secretos. Tipos: String, StringList, SecureString (cifrado KMS). Jerarquías, versioning
- Sin rotación automática propia. Más económico que Secrets Manager. Integración con EC2, Lambda, ECS via SDK/CLI
- Usar cuando: configuración general sin rotación, múltiples entornos, referencias en CloudFormation

---

## Cognito — Autenticación de Apps

- **User Pools** = directorio de usuarios para web/mobile. Sign-up/sign-in, MFA, UI personalizable. Retorna **JWT (JSON Web Token)**. Soporta federación con Google, Facebook, SAML, OIDC
- **Identity Pools** = proporciona **credenciales AWS temporales** para acceder a recursos AWS directamente. Soporta usuarios anónimos (guest). Usuarios autenticados via User Pool, Google, Facebook, SAML, OIDC asumen un IAM Role
- **Patrón combinado**: User Pool para autenticar → JWT → Identity Pool canjea JWT por credenciales AWS temporales → acceso directo a S3, DynamoDB, etc.

---

# DOMINIO 4: Design Cost-Optimized Architectures

---

## EC2 — Opciones de Compra

- **On-Demand** = sin compromiso, precio completo, facturación por segundo. Para: workloads imprevisibles, tests, short-term, primera vez
- **Spot** = capacidad no usada de AWS, hasta **90% descuento**. Se interrumpe con 2 minutos de aviso cuando AWS necesita la capacidad. Para: batch, rendering, ML training, CI/CD, análisis paralelo. **Nunca para workloads que no toleran interrupción**
- **Reserved Instances** = compromiso 1 o 3 años. Hasta 72% descuento:
  - **Standard RI**: instancia específica (familia, OS, tenancy), máximo descuento, no intercambiable
  - **Convertible RI**: puede cambiar tipo/OS/tenancy, menor descuento pero más flexible
  - **Scheduled RI**: para capacidad recurrente predecible (ej. batch diario). Mín 1,200h/año, 1 año de término
  - RI no usada se sigue facturando. Pueden venderse en Reserved Instance Marketplace
- **Savings Plans** = compromiso de $/hora (no de instancia), más flexible que RI:
  - **Compute Savings Plan**: EC2 + Lambda + Fargate. Hasta 66% descuento. Cualquier región, familia, OS
  - **EC2 Savings Plan**: familia específica en región específica. Hasta 72% descuento
- **Dedicated Host** = servidor físico completo. Para: licensing por socket/core (SQL Server, Oracle), compliance. Pagas por host
- **Dedicated Instance** = hardware dedicado pero sin gestionar el host. Sin garantías de licensing por core

### Guía de selección por workload
| Workload | Opción recomendada |
|---------|-------------------|
| Carga base 24/7 predecible | Reserved o Savings Plan |
| Picos impredecibles | On-Demand |
| Batch tolerante a interrupción | Spot Fleet |
| Licencias por core/socket | Dedicated Host |
| Desarrollo/test breve | On-Demand o Spot |
| Serverless / containers intermitentes | Fargate + Compute Savings Plan |

---

## S3 — Clases de Almacenamiento y Lifecycle

| Clase | Acceso esperado | AZs | Min. duración | Retrieval fee | Mejor para |
|-------|----------------|-----|---------------|--------------|-----------|
| **Standard** | Frecuente | 3+ | - | No | Datos activos en producción |
| **Standard-IA** | < 1x/mes | 3+ | 30 días | Sí | Backups accesibles, DR |
| **One Zone-IA** | < 1x/mes | 1 | 30 días | Sí | Datos reproducibles, thumbnails |
| **Glacier Instant** | Trimestral aprox. | 3+ | 90 días | Sí | Archivos médicos, media archive |
| **Glacier Flexible** | Anual aprox. | 3+ | 90 días | Sí (minutos/horas) | Archivos largo plazo |
| **Glacier Deep Archive** | Rarísimo | 3+ | 180 días | Sí (horas) | Compliance 7-10 años, archivos regulatorios |
| **Intelligent-Tiering** | Variable/desconocido | 3+ | - | No | Patrones de acceso impredecibles |
| **Express One Zone** | Muy frecuente, ms | 1 | - | No | ML, HPC, latencia crítica |

- **Lifecycle Policies** = transicionan objetos automáticamente. Dirección: Standard → IA → Glacier → Deep Archive (no vuelve atrás automáticamente). Mínimo 30 días en Standard antes de IA; 30 días más antes de Glacier
- **Intelligent-Tiering** = monitorea acceso y mueve objetos automáticamente. Sin retrieval fee. Pequeño coste de monitoreo por objeto. Ideal cuando el patrón de acceso es desconocido o varía
- **Pricing S3:** por GB almacenado/mes + por 1,000 requests (GET/PUT/etc.) + por GB de salida. Entrada (PUT) = gratis

---

## Bases de Datos — Optimización de Costes

- **DynamoDB On-Demand** = paga por millón de R/W units. Sin over-provisioning. Ideal para tráfico impredecible. Más caro que provisioned en carga alta sostenida
- **DynamoDB Provisioned + Auto Scaling** = RCU/WCU con scaling automático. Más barato para carga predecible. Configura min/max/target utilization
- **DynamoDB TTL** = expira items automáticamente **sin consumir WCU**. Solo marca para borrado asíncrono (puede tardar hasta 48h en borrarse). Ahorra almacenamiento, reduce costes de RCU en scans
- **Aurora Serverless v2** = escala en fracciones de ACU, puede pausar cuando no hay actividad. Para: DBs de desarrollo, multitenant con cargas variables, apps con tráfico impredecible
- **RDS Reserved Instances** = hasta 69% descuento para instancias de producción con uso predecible
- **Read Replicas** = escalar lecturas horizontalmente vs upgrade vertical del primario. Mucho más económico en read-heavy workloads
- **ElastiCache** = cachear resultados de DB costosos. ROI muy alto en workloads donde un 80% de lecturas son los mismos datos

---

## Arquitecturas Serverless — Beneficio de Coste

- **Lambda** = paga solo cuando ejecutas código (GB-segundos). $0 cuando no hay invocaciones. Para: event-driven, APIs con tráfico variable, microservicios. Optimizar coste: reducir tiempo de ejecución, calibrar memoria (benchmark: más RAM puede ser más barato si reduce tiempo)
- **Fargate** = paga por CPU/MEM durante la ejecución del container. Sin coste cuando no hay containers corriendo. Más económico que EC2 para cargas intermitentes o con baja utilización media
- **API Gateway** = pay-per-request. Caching reduce el número de invocaciones al backend (ahorra en Lambda y origen)
- **Step Functions Express** = pay por ejecución + duración. Para alto volumen de workflows cortos. Standard = pay por state transition (para workflows largos de menor volumen)
- **S3 como origen** de contenido estático vs EC2: sin servidor que mantener, sin coste de instancia idle

---

## Networking — Optimización de Transferencia de Datos

- **VPC Gateway Endpoints** (S3 y DynamoDB) = acceso privado **sin coste adicional** de transferencia. Elimina costes de NAT Gateway para tráfico a S3/DynamoDB. **Primera optimización a hacer**
- **NAT Gateway** = coste por hora + por GB procesado. Para cargas bajas: NAT Instance (EC2 pequeña) puede ser más barata (sin HA)
- **Data transfer entre AZs** = tiene coste. Minimizar con: arquitectura en una sola AZ para datos no críticos, VPC Endpoints
- **Data transfer hacia AWS** (inbound) = siempre gratis
- **CloudFront** = precio de salida desde edge generalmente menor que desde S3/EC2 directo. Reduce carga en origin (menos requests)
- **Direct Connect** = precio por GB de salida menor que internet para volúmenes altos. Se amortiza con ~1 Gbps sostenido
- **S3 Transfer Acceleration** = usar solo cuando la ganancia de velocidad justifica el coste adicional (clientes geográficamente distantes del bucket)

---

## Herramientas de Optimización de Costes

- **AWS Trusted Advisor** = recomendaciones en Cost Optimization, Performance, Security, Fault Tolerance, Service Limits. Checks avanzados requieren Support Business o superior
- **AWS Cost Explorer** = visualización y análisis de costes históricos y proyecciones. Identifica servicios/regiones más costosos
- **AWS Budgets** = alertas cuando el gasto real o proyectado supera umbrales definidos. Puede ejecutar acciones (stop instances)
- **AWS Compute Optimizer** = recomendaciones de right-sizing basadas en ML para EC2, Lambda, EBS, ECS. Identifica instancias over-provisioned

---

# REFERENCIA RÁPIDA

---

## Límites y Números Clave del Examen

| Servicio / Concepto | Número / Límite |
|--------------------|----------------|
| IAM Users por cuenta | 5,000 |
| IAM Groups por cuenta | 300 |
| Grupos por usuario IAM | 10 |
| Access Keys por usuario | 2 |
| S3 Bucket name | Globalmente único |
| S3 Buckets por cuenta | 100 soft / 1,000 hard |
| S3 Objeto tamaño máximo | 5 TB |
| S3 Multipart upload mínimo | 100 MB |
| S3 Versioning | No se puede desactivar, solo suspender |
| Default VPC CIDR | 172.31.0.0/16 |
| VPC CIDR range | /28 (mínimo, 16 IPs) a /16 (máximo, 65,536 IPs) |
| IPs reservadas por subnet | 5 (network, router +1, DNS +2, futuro +3, broadcast last) |
| NACLs por subnet | 1 |
| Subnets por NACL | Ilimitadas |
| IGW por VPC | 1 |
| RDS Multi-AZ failover | 60-120 segundos |
| RDS Read Replicas por instancia | 5 |
| RDS backup retención máxima | 35 días |
| Aurora réplicas de lectura | 15 |
| Aurora Global DB RPO | < 1 segundo |
| Aurora Global DB RTO | < 1 minuto |
| DynamoDB RCU (strong) | 1 lectura de 4KB/s |
| DynamoDB RCU (eventual) | 2 lecturas de 4KB/s |
| DynamoDB WCU | 1 escritura de 1KB/s |
| DynamoDB Streams ventana | 24 horas |
| DynamoDB LSIs por tabla | 5 (solo al crear la tabla) |
| DynamoDB GSIs por tabla | 20 (cualquier momento) |
| Lambda timeout máximo | 15 minutos (900s) |
| Lambda memoria rango | 128 MB a 10 GB |
| Lambda concurrencia default | 1,000 por región |
| SQS mensaje tamaño máximo | 256 KB |
| SQS retención default / máximo | 4 días / 14 días |
| SQS FIFO throughput | 300 TPS (3,000 con batching) |
| Kinesis retención default / máximo | 24 horas / 365 días |
| CloudTrail delay típico | ~15 minutos |
| CloudTrail Event History retención | 90 días |
| CloudFront TTL default | 24 horas |
| ACM cert para CloudFront | Debe estar en **us-east-1** |
| EC2 Hibernate RAM máxima | 150 GB |
| EC2 Hibernate duración máxima | 60 días |
| Shield Advanced | $3,000/mes, compromiso 1 año |
| Snowball capacidad | 50TB / 80TB (solo storage) |
| Snowball Edge Storage Optimized | 80TB + 24 vCPU + 32 GiB RAM |
| Snowmobile | Hasta 100PB por unidad |

---

## Decisión Rápida de Servicio

### Almacenamiento
| Necesidad | Servicio |
|-----------|---------|
| Objeto en la nube accesible por HTTP/API | S3 |
| Block storage para una instancia EC2 | EBS |
| Block de alta performance efímero | Instance Store |
| File system compartido Linux multi-instancia | EFS |
| File system Windows con AD / SMB | FSx for Windows |
| HPC / ML / POSIX alta performance | FSx for Lustre |
| Archivos largo plazo, compliance | S3 Glacier / Deep Archive |
| Backup centralizado multi-servicio | AWS Backup |

### Mensajería y Eventos
| Necesidad | Servicio |
|-----------|---------|
| Desacoplamiento async, worker pool | SQS |
| Fan-out / pub-sub / notificaciones | SNS |
| Streaming masivo, múltiples consumers | Kinesis Data Streams |
| Delivery de stream a S3/Redshift | Kinesis Firehose |
| AMQP/JMS/MQTT (migración legacy) | Amazon MQ |
| Eventos entre servicios, scheduling CRON | EventBridge |
| Workflow de pasos serverless | Step Functions |

### Bases de Datos
| Necesidad | Servicio |
|-----------|---------|
| Relacional OLTP | RDS |
| Relacional alto rendimiento + HA | Aurora |
| NoSQL key-value / document, ms latency | DynamoDB |
| Cache in-memory con HA y estructuras avanzadas | ElastiCache Redis |
| Cache simple y rápido multi-thread | ElastiCache Memcached |
| Microsegundo latency sobre DynamoDB | DAX |
| Data warehouse OLAP petabyte scale | Redshift |
| SQL ad-hoc serverless sobre S3 | Athena |
| Grafos | Neptune |
| MongoDB compatible | DocumentDB |
| ETL serverless | AWS Glue |

### Migración y Conectividad Híbrida
| Necesidad | Servicio |
|-----------|---------|
| VPN rápida (<1h) on-prem ↔ AWS | Site-to-Site VPN |
| Conexión dedicada alta velocidad y consistente | Direct Connect |
| Hub red multi-VPC con routing transitivo | Transit Gateway |
| Sync de archivos on-prem → AWS | DataSync |
| Migración masiva de datos (TB-PB) física | Snowball / Snowball Edge / Snowmobile |
| Bridge file on-prem ↔ S3 (NFS/SMB) | Storage Gateway File Mode |
| Backup en cinta → S3/Glacier | Storage Gateway Tape (VTL) |
| Volúmenes iSCSI on-prem con backup en cloud | Storage Gateway Volume |
| Migración de DB entre engines distintos | DMS (Database Migration Service) |
| Transferencia SFTP/FTPS/FTP → S3/EFS | AWS Transfer Family |

---

## Trampas Clásicas del Examen

- **Multi-AZ RDS** = solo HA, **no escala lecturas**. Para escalar lecturas → Read Replicas
- **SCP no otorgan permisos**, solo limitan. La **management account NO** se ve afectada por SCPs
- **NACL es stateless** = necesitas reglas para AMBAS direcciones (request + respuesta en ephemeral ports 1024-65535)
- **Instance Store** se pierde en **stop** (no solo en terminate). EBS persiste en stop
- **Lambda@Edge no soporta VPC ni Layers.** Solo Node.js y Python
- **CloudFront cert ACM** = obligatorio en **us-east-1**, independientemente de donde esté el origin
- **RDS restore** = siempre crea una **nueva instancia con nueva dirección**. No es in-place
- **DynamoDB GSI** = solo eventually consistent. Si necesitas strong consistency en el índice → LSI
- **VPC Peering no es transitivo.** Para routing transitivo → Transit Gateway
- **Direct Connect NO está cifrado** por defecto. Añadir VPN sobre DX para cifrado
- **Grupos IAM no pueden ser referenciados** en resource policies (bucket policies, etc.)
- **SNS + SQS Fan-out** ≠ Load Balancer. Fan-out = todos los consumers reciben todos los mensajes
- **Presigned URLs generadas con un Role** expiran cuando expiran las credenciales temporales del rol (puede ser antes de la URL)
- **S3 versioning no se puede desactivar** una vez activado, solo suspender
- **CloudTrail NO es real-time** (~15 min de delay). Para real-time usar EventBridge + CloudTrail
- **El OS en EC2 nunca ve la IPv4 pública** — vive solo en el IGW como traducción NAT

---

## Técnica para el Examen

**65 preguntas / 130 minutos (~2 min/pregunta). 72% para pasar.**

**Proceso por pregunta:**
1. Lee **la última frase** (la pregunta real) antes del escenario
2. Identifica la **restricción clave** del escenario
3. Elimina las 1-2 respuestas obviamente incorrectas primero
4. Aplica la restricción a las respuestas restantes

**Criterios de restricción y su implicación:**
| Restricción | Implicación |
|------------|-------------|
| "Mínimo cambio en el código / aplicación" | ElastiCache (misma API), DMS, Amazon MQ, RDS |
| "Sin gestionar servidores / mínimo overhead" | Lambda, Fargate, Aurora Serverless, DynamoDB |
| "Más económico para carga variable" | Serverless / Spot / On-Demand sobre Reserved |
| "Mayor rendimiento de red dedicado" | Direct Connect > VPN |
| "Acceso temporal a S3 para usuario externo" | Presigned URL |
| "Credenciales para servicio AWS accediendo a otro" | IAM Role (nunca access keys hardcodeadas) |
| "Escalar lecturas en base de datos" | Read Replicas (RDS/Aurora), no Multi-AZ |
| "Cumplimiento / datos no borrables" | Object Lock Compliance, Vault Lock (AWS Backup) |
| "Cifrado con control total de keys" | SSE-KMS con CMK o CloudHSM |
| "Datos sensibles en S3 / PII" | Amazon Macie |
| "Detectar amenazas sin configurar logs" | GuardDuty |
| "Flujo de trabajo multi-paso > 15 min" | Step Functions |
| "Múltiples cuentas, governance centralizada" | Organizations + Control Tower |

---

# DOMINIO EXTRA: Specialized Databases

---

## Amazon DocumentDB (with MongoDB Compatibility)

### Overview
- Fully managed **document database** service — stores, queries, and indexes JSON-like documents
- Compatible with **MongoDB 3.6, 4.0, 5.0, and 8.0** APIs (wire protocol compatible, NOT open-source MongoDB)
- DocumentDB 8.0 additionally supports MongoDB driver versions 6.0, 7.0, and 8.0
- **Decoupled compute and storage**: cluster volume (storage layer) is independent of instances (compute layer)

### Architecture
- **Cluster** = one primary instance (read/write) + up to **15 read replicas**
- **Cluster volume** spans **3 AZs** with **6 copies** of data for durability
- Storage auto-scales in **10 GB increments** up to **64 TB** — no performance impact
- Minimum storage: **10 GB**
- Replication lag to read replicas: typically **< 100 milliseconds**
- Replication type: **asynchronous**

### Cluster Types
- **Standard clusters**: single-region, up to 15 replicas
- **Elastic clusters**: MongoDB 5.0-compatible; support millions of reads/writes per second and petabyte-scale storage; horizontal sharding; NOT available in GovCloud or China regions; NOT supported on engine v8.0
- **Global clusters**: one primary region + up to **10 secondary read-only regions**; replication latency typically < 1 second; supports disaster recovery

### Key Features
- **ACID transactions**: supported from MongoDB 4.0 API — across multiple documents, statements, collections, and databases
- **Change streams**: track data changes in real time; available on primary and secondary instances (v5.0+); log retention: 1 hour–7 days (via `change_stream_log_retention_duration`)
- **TTL indexes**: auto-expire documents; deletions are best-effort, not guaranteed within an exact timeframe
- **In-place major version upgrades** supported
- New query planner delivering up to **10x performance improvements**

### Backup & Recovery
- **Automated backups** are always enabled; support **Point-in-Time Recovery (PITR)** up to **5 minutes** in the past
- Manual snapshots also available

### Security
- **Encryption in transit**: TLS (always on)
- **Encryption at rest**: AWS KMS-managed keys
- VPC isolation, IAM authentication

### Monitoring
- **Amazon SNS event subscriptions**: get notified on failover, config changes, backup completion, etc.
- CloudWatch metrics for performance monitoring

### Failover
- On primary failure, automatically promotes a replica to primary
- Promotion priority determines which replica is promoted first

### Pricing
- Billed on: **instance hours** (per instance class), **I/O requests** (per 1M/month), **backup storage** (per GiB/month)

### Exam Tips
- DocumentDB is **NOT** fully compatible with MongoDB — some APIs are unsupported; it emulates MongoDB behavior
- DocumentDB v3.6 reaches **end of life March 30, 2026**
- For **multi-region low-latency reads + DR** → use Global Clusters
- Elastic clusters for **horizontal scale** at petabyte scale
- PITR window is only **5 minutes** (not hours like RDS)
- Always distinguish: **read replicas** = scale reads; **Multi-AZ** is implicit in the shared storage architecture
- Change streams are useful for **event-driven architectures** (e.g., trigger Lambda on DB change)

---

## Amazon Neptune

### Overview
- Fully managed **graph database** service optimized for **highly connected datasets**
- Supports **billions of relationships** with **millisecond latency** traversals
- Two deployment models: **Provisioned** (select instance type) and **Serverless** (auto-scales compute/memory for variable workloads)

### Graph Models & Query Languages
| Model | Query Language | Use |
|-------|---------------|-----|
| Property Graph | **Apache TinkerPop Gremlin** | Social networks, recommendations |
| Property Graph | **openCypher** | Cypher-style declarative queries |
| RDF (Resource Description Framework) | **W3C SPARQL** | Knowledge graphs, semantic web |

### Architecture
- **Cluster** = one primary DB instance + up to **15 read replicas**
- Storage volume replicated **6 ways across 3 AZs** — self-healing (data blocks continuously scanned and auto-replaced on error)
- **ACID transactions** guaranteed
- **Read replicas** can act as **failover targets with no data loss**
- Failover: promotes replica with **highest priority tier** when primary fails

### Neptune Analytics
- Separate engine designed to analyze **tens of billions of relationships** and return **analytical results in seconds**
- Uses graph algorithms and vector search on large graph datasets in memory
- Distinct from Neptune Database (transactional) — Neptune Analytics is for **analytical/exploratory** graph workloads

### Global Database
- One primary cluster + up to **5 secondary read-only clusters** in other regions
- Enables **low-latency global reads** and cross-region disaster recovery

### Performance
- Supports **100,000s of queries per second** via read replicas
- Optimized for relationship traversal regardless of dataset size

### Backup & Restore
- **Automated backups** with PITR support
- Manual snapshots available

### Security
- **Encryption at rest**: AWS KMS
- **Encryption in transit**: TLS
- VPC network isolation
- IAM authentication and resource-based policies

### Monitoring
- CloudWatch metrics
- Audit logs available

### Pricing
- Based on: instance type hours, I/O requests, backup storage
- Serverless: billed on Neptune Capacity Units (NCUs) consumed

### Use Cases
- **Social networks**: model user interactions (follows, likes, comments)
- **Recommendation engines**: customer interest + purchase history graph
- **Knowledge graphs**: semantic search, ontologies
- **Fraud detection**: identify suspicious patterns in transaction relationships
- **Identity graphs**: link identities across data sources
- **Network/IT operations**: model infrastructure dependencies

### Exam Tips
- Neptune = **graph** database; choose it when the question mentions **relationships**, **nodes/edges**, **social networks**, **fraud detection**, or **knowledge graphs**
- Gremlin = **property graph** traversal; SPARQL = **RDF/semantic** data; openCypher = **declarative Cypher** syntax
- Neptune Serverless for **unpredictable/variable** graph workloads
- Neptune Analytics for **bulk analytical** graph queries — NOT transactional
- Global Database for **multi-region** graph apps
- Read replicas double as **automatic failover** targets with **no data loss**

---

## Amazon MemoryDB for Redis

### Overview
- Fully managed, **Redis-compatible** (and **Valkey-compatible**) **durable in-memory database** for microservices
- Provides **microsecond read** and **single-digit millisecond write** latency
- Unlike ElastiCache, MemoryDB is a **primary database** — data is durable, not just a cache layer
- Supports all Redis OSS / Valkey data types: strings, lists, sets, hashes, sorted sets, HyperLogLogs, bitmaps, streams, and **native JSON** (no extra cost)

### Architecture
- **Cluster** = one or more **shards**
- **Shard** = 1 to 6 nodes (1 primary write node + up to 5 read replicas)
- **Node** = smallest unit, runs on an EC2 instance
- Data stored entirely **in memory** for performance
- Durability via a **Multi-AZ transactional log** (persists every write to a distributed log across AZs before acknowledging success)
- This transactional log enables fast failover, recovery, and node restarts

### Replication & Consistency
- **Primary nodes**: **strong consistency**
- **Replica nodes**: **guaranteed eventual consistency**
- Up to **5 replicas in different AZs** for Multi-AZ HA
- Automatic failover: on primary failure, a replica is promoted to primary automatically

### Multi-Region
- One **primary cluster** (read/write) + up to **5 secondary clusters** (read-only) in other AWS Regions
- Supports **active-active** multi-region via Valkey (up to **99.999% availability**, microsecond reads, single-digit ms writes globally)
- Requires: **R7g nodes XL** and above; **Valkey engine v7.3+**

### Scaling
- **Horizontal**: add/remove nodes (shards)
- **Vertical**: change node types (e.g., r6g to r7g)

### Snapshots & Persistence
- **Automatic and on-demand snapshots** to S3
- Point-in-time recovery from snapshots
- The transactional log is the primary durability mechanism (NOT AOF like open-source Redis)

### Security
- **Encryption in transit**: TLS (server + client connections, replication between nodes)
- **Encryption at rest**: service-managed keys OR customer-managed KMS keys
- **Graviton2 instances**: always-on **256-bit DRAM encryption** in memory
- **Access Control Lists (ACLs)**: control authentication + authorization per user; each user has a password + access string defining allowed commands/data

### Pricing
- On-demand and **reserved nodes** (save up to **55%** with 1- or 3-year terms)
- **Valkey pricing is ~30% lower** than Redis OSS instance hour pricing
- Valkey: **no charge for data writes up to 10 TB/month**; $0.04/GB above 10 TB

### MemoryDB vs ElastiCache
| Feature | MemoryDB | ElastiCache |
|---------|----------|-------------|
| Primary purpose | **Primary database** (durable) | **Cache** (ephemeral) |
| Durability | Multi-AZ transactional log | Optional (RDB/AOF snapshots) |
| Data loss on failure | **None** | Possible |
| Latency | Microsecond reads | Microsecond reads |
| Use case | Microservices needing fast + durable store | Offload DB reads / session cache |

### Use Cases
- Real-time leaderboards and session management
- Microservices requiring a fast, durable primary data store
- Gaming state management
- Financial transaction processing requiring durability + speed
- Multi-region low-latency applications (Valkey Multi-Region)

### Exam Tips
- MemoryDB = **durable** Redis-compatible DB; ElastiCache = **cache** (not primary DB)
- Choose MemoryDB when the question asks for **Redis-compatible + durability + primary database**
- Multi-Region requires **Valkey** engine (not Redis OSS) and **R7g XL+** nodes
- ACLs control per-user command/key access — not just authentication
- Transactional log is the durability mechanism (analogous to a database WAL, not Redis AOF)

---

## Amazon Timestream

### Overview
- Fully managed, **purpose-built time series database** for storing and analyzing **trillions of time series data points per day**
- **Serverless** (for LiveAnalytics): no servers to manage, no capacity to provision — auto-scales
- Can ingest **tens of gigabytes per minute**; run SQL queries on **terabytes of data in seconds**

### Products (as of 2025)
| Product | Description | Status |
|---------|-------------|--------|
| **Timestream for InfluxDB** | Managed InfluxDB, real-time time series, single-digit ms query response, up to 99.9% availability | Recommended for new workloads |
| **Timestream for InfluxDB 3** | Leverages Apache Arrow + Apache DataFusion; next-gen InfluxDB engine | Available |
| **Timestream for LiveAnalytics** | Serverless SQL-based time series at massive scale | **No longer accepting new customers** as of June 20, 2025 |

> For new workloads, AWS recommends **Timestream for InfluxDB**.

### LiveAnalytics Storage Architecture (Two-Tier)
- **Memory Store**: stores recent/hot data; optimized for **fast point-in-time queries**; configurable retention (e.g., hours to days)
- **Magnetic Store**: stores historical/cold data; optimized for **fast analytical queries**; configurable retention (e.g., months to years)
- Data **automatically moves** from memory store to magnetic store when it ages past the memory retention threshold
- Data is **automatically deleted** from magnetic store when it ages past the magnetic store retention threshold
- Billed **separately** for: writes, memory store storage, magnetic store storage, and queries
- Magnetic store minimum billing: **100 GB per account per region per month**

### Key Features
- Native **time series functions** built into SQL queries
- **Adaptive query processing** — optimizes query execution automatically
- **Columnar data format** for efficient analytical queries
- **Scheduled queries** for real-time aggregations (materialized roll-ups)
- **Multi-measure records** (preferred over single-measure) for better performance and lower cost
- **Customer-defined partition keys** for controlling data distribution and improving query latency

### Data Modeling Best Practices
- Use **multi-measure records** over single-measure records (reduces I/O and cost)
- Choose **dimensions** for attributes that don't change over time (e.g., device ID, region)
- Use `measure_name` predicate in queries to **improve query latency**
- Leverage customer-defined **partition keys** to control data layout
- Set memory store retention based on **late-arriving data** requirements

### Integrations
- Ingest from: **AWS IoT Core**, Kinesis Data Streams, Amazon MSK (Kafka), Telegraf agents
- Query from: **Amazon QuickSight**, Grafana, JDBC/ODBC drivers, AWS SDK
- Works with **AWS Lambda** for event-driven processing

### Security
- Encryption at rest (KMS) and in transit (TLS)
- VPC endpoints supported
- IAM-based access control

### Use Cases
- **IoT sensor data**: temperature, pressure, telemetry at scale
- **DevOps monitoring**: application metrics, infrastructure metrics (CPU, memory over time)
- **Industrial telemetry**: manufacturing equipment monitoring
- **Financial data**: stock prices, trading metrics
- **Application performance monitoring (APM)**

### Exam Tips
- Timestream = **time series** data — choose when the question involves **IoT, sensor data, metrics over time, DevOps monitoring**
- Key differentiator: **automatic tiering** between memory (recent/fast) and magnetic (historical/analytical) stores
- LiveAnalytics is **serverless** — no infrastructure management
- LiveAnalytics **no longer accepts new customers** (June 2025); new workloads should use **Timestream for InfluxDB**
- Multi-measure records are **preferred** for performance and cost efficiency
- Timestream for InfluxDB offers **99.9% availability SLA** and single-digit millisecond query response

---

## Amazon EMR (Elastic MapReduce)

### Overview
- Managed **big data cluster platform** for processing and analyzing large datasets using distributed computing frameworks
- Runs on **EC2 instances** organized in clusters; supports **EC2 Spot, On-Demand, and Reserved** instances
- Also supports **EKS** (EMR on EKS) and **serverless** (EMR Serverless) deployment modes

### Node Types
| Node | Role | Stores HDFS Data? |
|------|------|------------------|
| **Primary (Master)** | Manages cluster, coordinates tasks, hosts resource manager | No (HDFS data) |
| **Core** | Runs tasks AND stores data in HDFS | Yes |
| **Task** | Runs tasks only — no HDFS storage; used for burst capacity | No |

- **High Availability**: launch cluster with **3 primary nodes** for HA; EMR auto-replaces failed primary nodes (same config + bootstrap actions)
- Task nodes are ideal for **Spot Instances** (no data loss if terminated)

### Supported Applications (EMR 7.x)
Spark, Hadoop, Hive, HBase, Presto, Trino, Flink, HCatalog, Hudi, Iceberg, Delta Lake, Tez, ZooKeeper, Pig, Oozie, Sqoop, and more.

### Storage Options
| Storage | Description | Persistence |
|---------|-------------|-------------|
| **HDFS** (Hadoop Distributed File System) | Distributed across core nodes; multiple copies per file; useful for caching intermediate results | **Ephemeral** — lost on cluster termination |
| **EMRFS** (EMR File System) | Access S3 directly as if it were a file system; integrates with Spark/Hadoop natively | **Persistent** — S3-backed |
| **EBS** | Attach EBS volumes to instances | Ephemeral (deleted when cluster terminates) |
| **Local instance store** | NVMe/SSD-backed instance storage | Ephemeral |

- **EMRFS + S3** is the recommended pattern for **persistent storage** — decouple storage from compute

### Cluster Lifecycle
- **Transient cluster**: auto-terminates after all steps complete — cost-effective for periodic jobs
- **Persistent cluster**: stays running for interactive/ad hoc queries (e.g., Hive, Spark Shell)

### Steps
- A **step** is a unit of work submitted to the cluster (e.g., a Spark job, a Hive query)
- Steps can run **sequentially or in parallel**
- Steps are submitted via Console, CLI, or API (`RunJobFlow`)

### Bootstrap Actions
- Scripts that run **after Amazon Linux AMI launch**, **before application installation**, and **before data processing begins**
- Used to install additional software, configure environment, download files, etc.
- Maximum: **16 bootstrap actions per cluster**

### Auto-Scaling
- **Managed scaling**: automatically adjusts number of core and task nodes based on workload metrics (YARN memory, pending containers)
- **Custom auto-scaling**: define rules based on CloudWatch metrics
- Task nodes preferred for auto-scaling (no HDFS risk if removed)

### Spot Instance Strategy
- Spot Instances can reduce costs by **up to 90%**
- Best used for **task nodes** (no HDFS data at risk)
- Spot interruption = instance terminated with **~2-minute warning**
- EMR handles Spot interruption gracefully for task nodes

### Security
- **Security configurations**: define encryption settings for at-rest and in-transit data
- **Encryption at rest**: EMRFS (S3 SSE/CSE), local disk encryption (EBS encryption, LUKS)
- **Encryption in transit**: TLS between nodes and between cluster and S3
- **IAM roles**:
  - EMR service role: permissions for EMR to call other AWS services
  - EC2 instance profile: permissions for EC2 nodes to access S3, DynamoDB, etc.
  - EMRFS IAM roles: fine-grained S3 access per identity/group
- **Kerberos authentication**: supported from EMR 5.10.0+ for cluster node authentication
- VPC support for network isolation; private subnets for added security

### Monitoring
- **CloudWatch** metrics and alarms
- **Ganglia** (open-source monitoring, installed as EMR application)
- Application-level logs (YARN, HDFS) available in S3 or accessible via SSH

### Pricing
- Pay per **EC2 instance hour** (EMR adds a small per-instance-hour fee on top of EC2 pricing)
- No upfront cost; use Reserved Instances for predictable workloads; Spot for burst/cost optimization
- **EMR Serverless**: pay per vCPU-hour and GB-hour of memory consumed

### Exam Tips
- EMR = **big data processing** — Spark, Hadoop, Hive, HBase, Presto, Flink at scale
- **HDFS is ephemeral** — for durable output, always write to **S3 via EMRFS**
- Task nodes = **no HDFS** = safe for Spot (terminated without data loss)
- Core nodes store HDFS — do NOT run core nodes on Spot (risk of data loss)
- 3 primary nodes = **HA mode** for the cluster manager
- Up to **16 bootstrap actions** per cluster
- Bootstrap actions run BEFORE application install and data processing
- For **cost optimization** with variable big data workloads: EMR + Spot task nodes + S3 (EMRFS)
- EMR Serverless = no cluster management; EMR on EKS = run on existing Kubernetes clusters
- Kerberos for **strong authentication** in regulated/enterprise environments
