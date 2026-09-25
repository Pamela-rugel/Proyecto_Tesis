# === DEPENDENCIAS ===
FROM node:20-alpine AS base
WORKDIR /app

FROM base AS deps
COPY dashboard_react/frontend/package*.json ./
RUN npm ci

FROM deps AS source
COPY dashboard_react/frontend/ .

# === BUILD (basePath /perfiles) ===
FROM source AS build
ARG VITE_API_URL=/perfiles
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build -- --base=/perfiles/

# === RUNTIME (nginx sirviendo archivos estaticos) ===
FROM nginx:1.27-alpine AS runtime
RUN rm -f /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
RUN printf 'server {\n\
  listen 80;\n\
  server_name _;\n\
  root /usr/share/nginx/html;\n\
  index index.html;\n\
\n\
  location /perfiles/ {\n\
    alias /usr/share/nginx/html/;\n\
    try_files $uri $uri/ /index.html;\n\
  }\n\
\n\
  location = /perfiles {\n\
    return 301 /perfiles/;\n\
  }\n\
}\n' > /etc/nginx/conf.d/app.conf
EXPOSE 80
