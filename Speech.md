# Speech Pitch – 5 Minutos
## Migración Plataforma Confirmación de Pagos

> **Duración objetivo:** ~5 minutos | **Ritmo:** natural, sin correr | **Tono:** claro y ejecutivo
> Marca los tiempos aproximados por sección para no pasarte.

---

## APERTURA (Slide 1 – Portada) · ~20 seg

"Buenos días a todos. Mi nombre es Samuel Daza y les voy a presentar el proyecto de **Migración de la Plataforma de Confirmación de Pagos**, una iniciativa del área de Fiduciaria para modernizar uno de los procesos más importantes en la operación diaria con nuestros clientes."

---

## CONTEXTO (Slide 2 – ¿Qué es Confirmación de Pagos?) · ~60 seg

"Primero, pongámonos en contexto. ¿Qué es la Confirmación de Pagos?

Cada vez que un cliente solicita un **retiro hacia un tercero**, un **traslado interno entre sus cuentas** o la **emisión de un cheque**, no basta con recibir la instrucción: hay que confirmar y respaldar la operación con el cliente antes de mover el dinero. Ese es el propósito de la Confirmación de Pagos: **notificar al cliente y validar la operación antes de liberar los recursos** hacia tesorería.

Esto funciona a través de dos flujos. El **flujo comercial** proviene de OyD Plus y FVP, que son los sistemas donde tenemos la información de los clientes; cuando nos llega una solicitud de retiro por correo electrónico a través de estos canales, si es una persona jurídica se envía un correo con confirmación de lectura, y si es persona natural se valida por SMS.

El **flujo de canales digitales** proviene de plataformas web o aplicativos donde el propio cliente solicita el retiro de fondos; en este caso la validación se hace por SMS, tanto para persona natural como jurídica.

Dependiendo de esa validación y de las reglas del negocio, la operación se libera automáticamente, se libera de forma manual, o se escala a un **Call Back**, que es una llamada telefónica directa al titular para confirmar la operación."

---

## EL PROBLEMA (Slide 3 – El Problema) · ~85 seg

"Hoy todo este proceso se apoya en una plataforma **externa** llamada **TopPoint**. TopPoint es el visor donde llegan todas las órdenes pendientes de confirmación; es la herramienta que usan los asesores para revisar cada caso y decidir si se libera o si requiere Call Back.

El problema es que esta plataforma tiene varias limitaciones importantes:

La primera son las **vulnerabilidades de seguridad**. La infraestructura sobre la que corre TopPoint es antigua, está quedando obsoleta y no está a la vanguardia de la tecnología actual, lo que representa un riesgo para una operación tan sensible como el manejo de pagos.

La segunda es que **no nos permite evolucionar**. Estas mismas limitaciones de seguridad impiden que se habiliten los permisos de las áreas mientras no se resuelvan, y sin esos permisos no podemos incorporar nuevas tecnologías ni canales de verificación. Quedamos bloqueados hasta que la situación se resuelva.

La tercera es la **falta de gestión de reglas**. Hoy las reglas de negocio están definidas y controladas por el proveedor, TopPoint. Y como no podemos evolucionar la plataforma, tampoco podemos ajustar esas reglas por nuestra cuenta en este momento.

La cuarta es el **control de fraude**: necesitamos mecanismos de validación más robustos que la plataforma actual no nos ofrece.

Y la quinta, muy importante: **no hay trazabilidad**. Hoy un solo asesor entra al visor, ve todas las órdenes al mismo tiempo y toma cualquiera para revisarla. Como no hay asignación individual, no queda registro de quién revisó qué, cuándo ni qué decisión tomó. Y no solo eso: tampoco tenemos visibilidad sobre indicadores clave del proceso, como cuántas órdenes están pendientes de confirmar, cuántas se han confirmado en el día de hoy, cuántas requirieron Call Back y cuántas se verificaron de forma automática. Tampoco sabemos cuántas operaciones llegaron por cada canal o sistema, ni de qué tipo de fondo se trata —Fondos de Inversión Colectiva, órdenes permanentes, divisas o retiros de PA—, ni qué colaboradores de las áreas de Negocio y Onboarding con clientes gestionaron cada orden, con qué método y desde qué origen. Sin toda esa información, es muy difícil controlar y medir el proceso."

---

## LA SOLUCIÓN (Slide – Solución y Alcance) · ~55 seg

"La solución es **dejar de depender de TopPoint** y construir un **módulo propio dentro de Ozono**, nuestra plataforma corporativa interna, integrado con el Hub de Comunicaciones.

Este módulo se apoya en cinco pilares:

Uno, **módulo propio**: desarrollado internamente, bajo nuestro control.

Dos, **reglas adaptables**: el negocio podrá parametrizar las reglas según sus necesidades, sin depender de un tercero.

Tres, **nuevas tecnologías**: quedamos habilitados para incorporar biometría, mensajería de doble vía o mecanismos OTP conforme lo requieran las reglas de negocio.

Cuatro, **trazabilidad**: cada acción quedará registrada por usuario y por operación.

Y cinco, **seguridad**: un entorno moderno, bajo los estándares de BTG."

---

## LÍNEA DE TIEMPO (Slide – Línea de Tiempo) · ~45 seg

"El proyecto está planteado a **6 meses**.

El **mes 1** fue de introducción: entender el proceso, los sistemas involucrados y alinear a los stakeholders. Y aquí vale la pena aclarar: los **stakeholders** son todas las personas y áreas que tienen interés en el proyecto o se ven afectadas por él; en nuestro caso, el área de Fiduciaria, los asesores que operan el visor, el equipo comercial y tecnología. Alinearlos significa ponerlos a todos de acuerdo sobre el alcance, las expectativas y las prioridades desde el inicio.

Actualmente estamos en la **fase final del mes 2**, dedicado al análisis: levantando reglas de negocio, flujos y requerimientos. Los **meses 3 y 4** serán la etapa de diseño y desarrollo, donde definimos la arquitectura y las interfaces y construimos el módulo completo: el visor, la asignación de casos, las reglas, las notificaciones y el Call Back. El **mes 5** será de pruebas, y en el **mes 6** salimos a producción con un periodo de convivencia con TopPoint antes de apagarlo definitivamente."

---

## IMPACTO (Slide – Impacto Esperado) · ~60 seg

"Finalmente, ¿qué impacto esperamos?

**Un entorno seguro**: un sistema moderno y protegido, sin los riesgos de la infraestructura actual.

**Una reducción cercana al 30% en el tiempo de Call Back**, al sustituir progresivamente las llamadas por mecanismos de confirmación más eficientes. Esto libera tiempo valioso del equipo para tareas de mayor valor.

**Validación de datos más precisa**, al consumir información directamente de nuestras fuentes corporativas.

Y **autonomía total** para evolucionar el proceso sin depender de cronogramas externos.

Pero más allá de lo operativo, este proyecto genera valor de negocio en tres frentes claros:

**Reducción de costos**: al migrar a una plataforma propia, dejamos de pagar por el servicio de un proveedor externo, eliminando ese costo recurrente.

**Ahorro de tiempo**: además de la reducción en Call Back, la asignación individual de casos distribuye la carga entre todo el equipo, en lugar de concentrarla en un solo asesor.

Y **cumplimiento de riesgos operativos**: al modernizar la seguridad y tener trazabilidad completa de cada operación, fortalecemos el control interno sobre un proceso crítico."

---

## CIERRE (Slide – Muchas Gracias) · ~20 seg

"En resumen: tomamos un proceso crítico que hoy depende de una plataforma externa con limitaciones, y lo traemos a casa, con un módulo propio, más seguro, con trazabilidad completa, reglas flexibles y la capacidad de evolucionar cuando el negocio lo necesite.

Muchas gracias. Quedo atento a sus preguntas."

---

## NOTAS DE APOYO

- **Distribución de tiempo total:** ~5 min (20s + 60s + 85s + 55s + 45s + 60s + 20s ≈ 5:25). Habla con calma; si vas justo, recorta la enumeración de indicadores de trazabilidad y la lista de tipos de fondo.
- Si necesitas ganar tiempo, en la sección de trazabilidad menciona solo 3-4 indicadores de ejemplo en vez de toda la lista.
- **Conceptos que deben quedar claros** (ya integrados en el guion):
  - Qué es Confirmación de Pagos → notificar y validar antes de liberar fondos.
  - Qué es TopPoint → plataforma externa / visor actual de órdenes.
  - Flujo comercial → viene de OyD Plus y FVP (sistemas con info de clientes), solicitudes por correo.
  - Flujo de canales digitales → plataformas web o aplicativos donde el cliente pide el retiro.
  - Por qué no hay trazabilidad → un asesor ve todo, sin asignación individual ni registro; falta de visibilidad de indicadores y métricas del proceso.
  - Qué son stakeholders y cómo se alinean → interesados del proyecto, puestos de acuerdo en alcance y prioridades.
- **Al hablar de seguridad:** mantente en "infraestructura antigua y obsoleta". No entres en detalles de vulnerabilidades específicas.
- **Sobre no evolucionar:** las limitaciones de seguridad bloquean los permisos de las áreas; sin permisos no se pueden incorporar nuevas tecnologías.
- **Sobre las reglas:** están definidas y controladas por TopPoint; al no poder evolucionar, no se pueden ajustar por ahora.
- **No menciones** temas de definiciones de reglas pendientes internas ni aprobaciones externas específicas.
