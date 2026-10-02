"""Perfiles del personal a partir de las evidencias (DEC-045).

Etapa: clustering multivista con Similarity Network Fusion (SNF) sobre tres vistas del mismo
perfil de cada persona:
    V1 semantica de trayectoria y gestion  (embeddings de evidencias de cargos y actividades)
    V2 semantica academico-tematica        (embeddings de formacion, investigacion, docencia...)
    V3 estructurada                        (variables numericas agregadas de los atributos)

Modulos:
    embeddings.py      embedding de cada texto unico de evidencia (BAAI/bge-m3), persistido
    vistas.py          construccion de las tres vistas por persona
    snf.py             Similarity Network Fusion (Wang et al., 2014)
    clustering.py      clustering espectral sobre la red fusionada, pertenencias, medoides, t-SNE
    interpretacion.py  caracteristicas y descripcion de cada cluster
    construir.py       orquesta todo y persiste los resultados versionados en data/perfiles/
"""
