FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
ENV GENERATE_SOURCEMAP=false
RUN npm run build

FROM node:20-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/build ./build
RUN chown -R node:node /app
USER node
EXPOSE 3000
CMD ["serve", "-s", "build", "-l", "3000"]
