# Build stage
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# Serve stage
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/nginx.conf.template

EXPOSE 80

# We run envsubst ourselves (rather than dropping the template into
# /etc/nginx/templates/) so we can restrict substitution to $API_UPSTREAM only.
# The nginx image's built-in envsubst has no variable filter, which means it
# would also replace nginx built-in variables like $uri, $proxy_host, and
# $remote_addr — silently corrupting the config and breaking reverse-proxy.
CMD ["/bin/sh", "-c", "envsubst '$API_UPSTREAM' < /etc/nginx/nginx.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
