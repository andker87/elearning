FROM node:20-alpine AS build
WORKDIR /app
# npm ci installa esattamente le versioni del package-lock.json: build riproducibili
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Le pagine sono file statici: le serve nginx (senza privilegi), niente Node in produzione.
FROM nginxinc/nginx-unprivileged:alpine
USER root
RUN apk upgrade --no-cache
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html
USER nginx
EXPOSE 3000
