# Usuarios iniciales de evaluación

`python 06_inicializar_plataforma.py --aplicar` crea **tres usuarios**, uno por
cada empresa existente en el histórico. El nombre es `evaluador_<empresa_id>`
en minúsculas; caracteres distintos de letras, números y guion bajo se sustituyen
por guion bajo. Cada usuario tiene una única membresía de **supervisor** de su
empresa. No son superusuarios ni pueden entrar al administrador de Django.

Los nombres exactos, las empresas y las contraseñas aleatorias se guardan en
`local-private/usuarios.md`. Ese archivo está excluido de Git. Es el documento
que debe consultarse localmente para iniciar sesión en `/accounts/login/`.

Repetir la inicialización conserva las contraseñas y no duplica usuarios.
Las nuevas contraseñas solo se generan para usuarios nuevos. Si ya existe un
usuario con ese nombre vinculado a otra empresa, se detiene la inicialización.
El script también aplica las migraciones, crea el rol SQL restringido si falta,
actualiza `.env` y sincroniza los leads históricos.

Requisitos: histórico cargado con las tres empresas, `SUPABASE_DB_URL`
administrativa en `.env` y dependencias del proyecto instaladas. La aplicación
usa `DJANGO_DATABASE_URL` restringida; las migraciones usan la administrativa.
