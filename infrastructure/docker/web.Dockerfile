FROM node:22-alpine AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
COPY apps/admin/package.json apps/admin/package.json
COPY packages/shared_types/package.json packages/shared_types/package.json
COPY packages/validation/package.json packages/validation/package.json
RUN npm ci

FROM dependencies AS build
COPY apps/web apps/web
COPY packages/shared_types packages/shared_types
COPY packages/validation packages/validation
# The web build imports the reviewed consumer category taxonomy
# (apps/web/lib/procedureCategories.ts -> data/consumer_procedure_categories.json).
COPY data/consumer_procedure_categories.json data/consumer_procedure_categories.json
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_SITE_URL
ARG APP_ENV=beta
ARG SEO_INDEXING_ENABLED=false
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL API_PUBLIC_URL=$NEXT_PUBLIC_API_URL
ENV APP_ENV=$APP_ENV SEO_INDEXING_ENABLED=$SEO_INDEXING_ENABLED
RUN npm run build --workspace @carecompare/web

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production PORT=8080 HOSTNAME=0.0.0.0
RUN addgroup --system --gid 10001 carevero && adduser --system --uid 10001 --ingroup carevero carevero
COPY --from=build --chown=carevero:carevero /app/apps/web/.next/standalone ./
COPY --from=build --chown=carevero:carevero /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=carevero:carevero /app/apps/web/public ./apps/web/public
USER carevero
EXPOSE 8080
CMD ["node", "apps/web/server.js"]
