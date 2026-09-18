export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json({
    supabase_url: Boolean(process.env.SUPABASE_URL),
    supabase_service_role: Boolean(process.env.SUPABASE_SERVICE_ROLE_KEY),
    api_football_key: Boolean(process.env.API_FOOTBALL_KEY),
    api_football_team_id: Boolean(process.env.API_FOOTBALL_TEAM_ID),
    cron_secret: Boolean(process.env.CRON_SECRET),
  });
}
