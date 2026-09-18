import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const TEAM_ID = Number(process.env.API_FOOTBALL_TEAM_ID ?? "117");
const TIMEZONE = process.env.API_FOOTBALL_TIMEZONE ?? "America/Sao_Paulo";

const CAMPEONATOS_OFICIAIS = new Set([
  "Mineiro",
  "Brasileiro",
  "Copa do Brasil",
  "Copa Libertadores",
  "Copa Sul-Americana",
  "Supercopa do Brasil",
]);

type JsonObject = Record<string, any>;

function normalizeName(value: unknown): string {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\b(fc|ec|sc|mg|sp|rj|pr|rs|ba|ce|go)\b/g, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function sameClub(a: unknown, b: unknown): boolean {
  const aa = normalizeName(a);
  const bb = normalizeName(b);
  if (!aa || !bb) return false;
  if (aa === bb || aa.includes(bb) || bb.includes(aa)) return true;

  const at = new Set(aa.split(" ").filter((x) => x.length >= 3));
  const bt = new Set(bb.split(" ").filter((x) => x.length >= 3));
  const comuns = [...at].filter((x) => bt.has(x)).length;
  return comuns >= Math.min(2, Math.min(at.size, bt.size));
}

function isGaloName(value: unknown): boolean {
  const nome = normalizeName(value);
  return (
    nome.includes("atletico mineiro") ||
    nome === "atletico" ||
    nome === "atletico mineiro"
  );
}

function galoHomeGame(game: JsonObject): boolean {
  const teamIds = game?.metadados?.sofascore?.team_ids ?? {};
  if (String(teamIds?.home ?? "") === "1977") return true;
  if (String(teamIds?.away ?? "") === "1977") return false;
  return isGaloName(game?.mandante);
}

function gameOpponent(game: JsonObject): string {
  return galoHomeGame(game) ? String(game.visitante ?? "") : String(game.mandante ?? "");
}

function fixtureOpponent(fixture: JsonObject): string {
  const homeId = Number(fixture?.teams?.home?.id);
  return homeId === TEAM_ID
    ? String(fixture?.teams?.away?.name ?? "")
    : String(fixture?.teams?.home?.name ?? "");
}

function diffHours(a: string, b: string): number {
  const aa = new Date(a).getTime();
  const bb = new Date(b).getTime();
  if (!Number.isFinite(aa) || !Number.isFinite(bb)) return Number.POSITIVE_INFINITY;
  return Math.abs(aa - bb) / 3_600_000;
}

function matchFixture(game: JsonObject, fixtures: JsonObject[]): JsonObject | null {
  const rival = gameOpponent(game);
  const candidatos = fixtures
    .filter((fixture) => sameClub(rival, fixtureOpponent(fixture)))
    .map((fixture) => ({
      fixture,
      diff: diffHours(String(game.inicio_em), String(fixture?.fixture?.date ?? "")),
    }))
    .filter((item) => item.diff <= 40)
    .sort((a, b) => a.diff - b.diff);

  return candidatos[0]?.fixture ?? null;
}

function mapStatus(short: string): string {
  const status = String(short ?? "").toUpperCase();
  if (["FT", "AET", "PEN"].includes(status)) return "finalizado";
  if (["1H", "HT", "2H", "ET", "BT", "P", "LIVE"].includes(status)) return "ao_vivo";
  if (["PST", "CANC", "SUSP", "INT", "ABD", "AWD", "WO"].includes(status)) return "adiado";
  return "agendado";
}

function numberValue(value: unknown): number | null {
  if (value == null) return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const clean = String(value).replace("%", "").replace(",", ".").trim();
  const n = Number(clean);
  return Number.isFinite(n) ? n : null;
}

function supabaseHeaders() {
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY ?? "";
  return {
    apikey: key,
    Authorization: `Bearer ${key}`,
    "Content-Type": "application/json",
  };
}

async function supabaseFetch(path: string, init: RequestInit = {}) {
  const base = process.env.SUPABASE_URL ?? "";
  if (!base || !process.env.SUPABASE_SERVICE_ROLE_KEY) {
    throw new Error("Supabase não configurado no Vercel.");
  }

  const headers = new Headers(supabaseHeaders());
  new Headers(init.headers).forEach((value, key) => headers.set(key, value));

  const response = await fetch(`${base}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Supabase ${response.status}: ${text.slice(0, 500)}`);
  }

  if (response.status === 204) return null;
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

async function apiFootball(path: string) {
  const key = process.env.API_FOOTBALL_KEY ?? "";
  if (!key) throw new Error("API_FOOTBALL_KEY não configurada no Vercel.");

  const response = await fetch(`https://v3.football.api-sports.io${path}`, {
    cache: "no-store",
    headers: {
      "x-apisports-key": key,
      Accept: "application/json",
    },
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(`API-Football ${response.status}`);
  }
  if (data?.errors && Object.keys(data.errors).length > 0) {
    throw new Error(`API-Football: ${JSON.stringify(data.errors)}`);
  }

  return data?.response ?? [];
}

async function sofaGet(path: string): Promise<JsonObject | null> {
  const response = await fetch(`https://www.sofascore.com/api/v1${path}`, {
    cache: "no-store",
    headers: {
      "User-Agent": "Mozilla/5.0",
      Accept: "application/json, text/plain, */*",
      Referer: "https://www.sofascore.com/",
    },
  }).catch(() => null);

  if (!response?.ok) return null;
  return await response.json().catch(() => null);
}

function sofaEventId(game: JsonObject): number | null {
  const meta = game?.metadados?.sofascore?.event_id;
  const direct = Number(meta);
  if (Number.isFinite(direct)) return direct;

  const externo = String(game?.id_externo ?? "");
  if (externo.startsWith("sofascore:")) {
    const n = Number(externo.split(":", 2)[1]);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function sofaPlayers(lineups: JsonObject, lado: "home" | "away"): JsonObject[] {
  const players = Array.isArray(lineups?.[lado]?.players) ? lineups[lado].players : [];
  return players
    .map((item: JsonObject) => {
      const player = item?.player ?? {};
      const id = Number(player?.id);
      if (!Number.isFinite(id)) return null;
      return {
        jogador_id: id,
        nome: String(player?.name ?? player?.shortName ?? "Jogador"),
        nome_guerra: String(player?.shortName ?? player?.name ?? "Jogador"),
        posicao: player?.position ?? item?.position ?? null,
        camisa: item?.shirtNumber ?? null,
        titular: !Boolean(item?.substitute),
        estatisticas: item?.statistics ?? {},
      };
    })
    .filter((item: JsonObject | null): item is JsonObject => item !== null);
}

function statMap(teamBlock: JsonObject): Map<string, unknown> {
  return new Map(
    (Array.isArray(teamBlock?.statistics) ? teamBlock.statistics : []).map((item: JsonObject) => [
      String(item?.type ?? ""),
      item?.value,
    ])
  );
}

function apiFootballCollective(statsResponse: JsonObject[], fixture: JsonObject): JsonObject {
  const homeId = Number(fixture?.teams?.home?.id);
  const awayId = Number(fixture?.teams?.away?.id);
  const home = statsResponse.find((x) => Number(x?.team?.id) === homeId) ?? {};
  const away = statsResponse.find((x) => Number(x?.team?.id) === awayId) ?? {};
  const h = statMap(home);
  const a = statMap(away);

  const definitions = [
    ["Match overview", "ballPossession", "Ball Possession", "Ball Possession"],
    ["Match overview", "fouls", "Fouls", "Fouls"],
    ["Match overview", "yellowCards", "Yellow Cards", "Yellow Cards"],
    ["Match overview", "redCards", "Red Cards", "Red Cards"],
    ["Attack", "totalShotsOnGoal", "Total Shots", "Total Shots"],
    ["Attack", "shotsOnGoal", "Shots on Goal", "Shots on Goal"],
    ["Attack", "shotsOffGoal", "Shots off Goal", "Shots off Goal"],
    ["Attack", "blockedScoringAttempt", "Blocked Shots", "Blocked Shots"],
    ["Attack", "totalShotsInsideBox", "Shots insidebox", "Shots insidebox"],
    ["Attack", "totalShotsOutsideBox", "Shots outsidebox", "Shots outsidebox"],
    ["Attack", "cornerKicks", "Corner Kicks", "Corner Kicks"],
    ["Attack", "offsides", "Offsides", "Offsides"],
    ["Attack", "expectedGoals", "expected_goals", "Expected Goals"],
    ["Goalkeeping", "goalkeeperSaves", "Goalkeeper Saves", "Goalkeeper Saves"],
    ["Passes", "passes", "Total passes", "Total passes"],
    ["Passes", "accuratePasses", "Passes accurate", "Passes accurate"],
  ] as const;

  const groups = new Map<string, JsonObject[]>();

  for (const [group, key, source, name] of definitions) {
    const homeValue = h.get(source);
    const awayValue = a.get(source);
    if (homeValue == null && awayValue == null) continue;

    const item = {
      key,
      name,
      home: homeValue,
      away: awayValue,
      homeValue,
      awayValue,
    };

    if (!groups.has(group)) groups.set(group, []);
    groups.get(group)!.push(item);
  }

  return {
    statistics: [
      {
        period: "ALL",
        groups: [...groups.entries()].map(([groupName, statisticsItems]) => ({
          groupName,
          statisticsItems,
        })),
      },
    ],
    origem: "api-football",
  };
}

function apiFootballPlayers(playersResponse: JsonObject[], fixture: JsonObject): JsonObject[] {
  const galo = playersResponse.find((x) => Number(x?.team?.id) === TEAM_ID);
  const players = Array.isArray(galo?.players) ? galo.players : [];

  return players
    .map((row: JsonObject) => {
      const p = row?.player ?? {};
      const s = Array.isArray(row?.statistics) ? row.statistics[0] ?? {} : {};
      const games = s?.games ?? {};
      const passes = s?.passes ?? {};
      const shots = s?.shots ?? {};
      const goals = s?.goals ?? {};
      const tackles = s?.tackles ?? {};
      const duels = s?.duels ?? {};
      const dribbles = s?.dribbles ?? {};
      const fouls = s?.fouls ?? {};
      const penalty = s?.penalty ?? {};

      const totalPass = numberValue(passes?.total);
      const accuracyPct = numberValue(passes?.accuracy);
      const accuratePass =
        totalPass != null && accuracyPct != null
          ? Math.round((totalPass * accuracyPct) / 100)
          : null;

      const duelTotal = numberValue(duels?.total);
      const duelWon = numberValue(duels?.won);
      const totalShots = numberValue(shots?.total);
      const shotsOn = numberValue(shots?.on);

      const estatisticas: JsonObject = {
        minutesPlayed: numberValue(games?.minutes),
        rating: numberValue(games?.rating),
        goals: numberValue(goals?.total),
        goalAssist: numberValue(goals?.assists),
        saves: numberValue(goals?.saves),
        totalShots,
        onTargetScoringAttempt: shotsOn,
        shotOffTarget:
          totalShots != null && shotsOn != null ? Math.max(0, totalShots - shotsOn) : null,
        totalPass,
        accuratePass,
        keyPass: numberValue(passes?.key),
        totalTackle: numberValue(tackles?.total),
        outfielderBlock: numberValue(tackles?.blocks),
        interceptionWon: numberValue(tackles?.interceptions),
        duelWon,
        duelLost:
          duelTotal != null && duelWon != null ? Math.max(0, duelTotal - duelWon) : null,
        totalContest: numberValue(dribbles?.attempts),
        wonContest: numberValue(dribbles?.success),
        challengeLost: numberValue(dribbles?.past),
        fouls: numberValue(fouls?.committed),
        wasFouled: numberValue(fouls?.drawn),
        penaltyWon: numberValue(penalty?.won),
        penaltyConceded: numberValue(penalty?.commited),
        penaltyMiss: numberValue(penalty?.missed),
        penaltySave: numberValue(penalty?.saved),
      };

      for (const key of Object.keys(estatisticas)) {
        if (estatisticas[key] == null) delete estatisticas[key];
      }

      const id = Number(p?.id);
      if (!Number.isFinite(id)) return null;

      return {
        jogador_id: id,
        nome: String(p?.name ?? "Jogador"),
        nome_guerra: String(p?.name ?? "Jogador"),
        posicao: games?.position ?? null,
        camisa: games?.number ?? null,
        titular: !Boolean(games?.substitute),
        estatisticas,
      };
    })
    .filter((item: JsonObject | null): item is JsonObject => item !== null);
}

async function saveStats(
  game: JsonObject,
  eventId: number,
  lado: "home" | "away",
  coletiva: JsonObject,
  jogadores: JsonObject[]
) {
  return await supabaseFetch("/rest/v1/rpc/cron_salvar_estatisticas_api_football", {
    method: "POST",
    body: JSON.stringify({
      p_jogo_id: game.id,
      p_event_id: eventId,
      p_lado_galo: lado,
      p_coletiva: coletiva,
      p_jogadores: jogadores,
    }),
  });
}

async function isAuthorized(request: NextRequest): Promise<boolean> {
  const auth = request.headers.get("authorization") ?? "";
  const cronSecret = process.env.CRON_SECRET ?? "";

  if (cronSecret && auth === `Bearer ${cronSecret}`) return true;
  if (!auth.startsWith("Bearer ")) return false;

  const supabaseUrl = process.env.SUPABASE_URL ?? "";
  if (!supabaseUrl) return false;

  const validation = await fetch(
    `${supabaseUrl}/functions/v1/central-admin-api/acessos?periodo=hora`,
    {
      headers: { Authorization: auth },
      cache: "no-store",
    }
  ).catch(() => null);

  return Boolean(validation?.ok);
}

export async function GET(request: NextRequest) {
  if (!(await isAuthorized(request))) {
    return Response.json({ detail: "Não autorizado." }, { status: 401 });
  }

  const year = new Date().getUTCFullYear();
  const from = `${year}-01-01T00:00:00.000Z`;
  const to = `${year + 1}-01-01T00:00:00.000Z`;

  const result = {
    ano: year,
    jogos_atualizados: 0,
    pendentes_estatisticas: 0,
    estatisticas_salvas: 0,
    sofascore: 0,
    api_football: 0,
    erros: [] as string[],
  };

  try {
    const fixtures = await apiFootball(
      `/fixtures?team=${TEAM_ID}&season=${year}&timezone=${encodeURIComponent(TIMEZONE)}`
    );

    const select = encodeURIComponent(
      "id,id_externo,mandante,visitante,inicio_em,status,gols_mandante,gols_visitante,estadio,cidade,metadados,competicao:competicoes(nome)"
    );

    const jogos = await supabaseFetch(
      `/rest/v1/jogos?select=${select}&inicio_em=gte.${encodeURIComponent(from)}&inicio_em=lt.${encodeURIComponent(to)}`
    );

    const oficiais = (Array.isArray(jogos) ? jogos : []).filter((game: JsonObject) => {
      const comp = Array.isArray(game?.competicao) ? game.competicao[0] : game?.competicao;
      return CAMPEONATOS_OFICIAIS.has(String(comp?.nome ?? ""));
    });

    const statsRows = await supabaseFetch(
      "/rest/v1/estatisticas_jogos_sofascore?select=jogo_id&limit=10000"
    );
    const comStats = new Set(
      (Array.isArray(statsRows) ? statsRows : []).map((row: JsonObject) => String(row.jogo_id))
    );

    for (const game of oficiais) {
      const fixture = matchFixture(game, fixtures);
      if (!fixture) continue;

      const short = String(fixture?.fixture?.status?.short ?? "");
      const fixtureDate = String(fixture?.fixture?.date ?? game.inicio_em);
      const goalsHome = numberValue(fixture?.goals?.home);
      const goalsAway = numberValue(fixture?.goals?.away);

      const mergedMeta = {
        ...(game?.metadados ?? {}),
        api_football: {
          fixture_id: fixture?.fixture?.id ?? null,
          team_ids: {
            home: fixture?.teams?.home?.id ?? null,
            away: fixture?.teams?.away?.id ?? null,
          },
          league_id: fixture?.league?.id ?? null,
          status_short: short,
          atualizado_em: new Date().toISOString(),
        },
      };

      await supabaseFetch(`/rest/v1/jogos?id=eq.${encodeURIComponent(String(game.id))}`, {
        method: "PATCH",
        headers: { Prefer: "return=minimal" },
        body: JSON.stringify({
          inicio_em: fixtureDate,
          status: mapStatus(short),
          gols_mandante: goalsHome,
          gols_visitante: goalsAway,
          estadio: fixture?.fixture?.venue?.name ?? game.estadio ?? null,
          cidade: fixture?.fixture?.venue?.city ?? game.cidade ?? null,
          metadados: mergedMeta,
          atualizado_em: new Date().toISOString(),
        }),
      });
      result.jogos_atualizados += 1;
    }

    const finalizadosPendentes = oficiais.filter((game: JsonObject) => {
      const fixture = matchFixture(game, fixtures);
      if (!fixture) return false;
      return mapStatus(String(fixture?.fixture?.status?.short ?? "")) === "finalizado" &&
        !comStats.has(String(game.id));
    });

    result.pendentes_estatisticas = finalizadosPendentes.length;

    for (const game of finalizadosPendentes) {
      const fixture = matchFixture(game, fixtures);
      if (!fixture) continue;

      const lado: "home" | "away" =
        Number(fixture?.teams?.home?.id) === TEAM_ID ? "home" : "away";

      const sofaId = sofaEventId(game);
      if (sofaId != null) {
        const [coletivaSofa, lineupsSofa] = await Promise.all([
          sofaGet(`/event/${sofaId}/statistics`),
          sofaGet(`/event/${sofaId}/lineups`),
        ]);

        if (coletivaSofa && lineupsSofa) {
          await saveStats(
            game,
            sofaId,
            lado,
            coletivaSofa,
            sofaPlayers(lineupsSofa, lado)
          );
          result.estatisticas_salvas += 1;
          result.sofascore += 1;
          continue;
        }
      }

      try {
        const fixtureId = Number(fixture?.fixture?.id);
        const [collectiveResponse, playerResponse] = await Promise.all([
          apiFootball(`/fixtures/statistics?fixture=${fixtureId}`),
          apiFootball(`/fixtures/players?fixture=${fixtureId}`),
        ]);

        await saveStats(
          game,
          fixtureId,
          lado,
          apiFootballCollective(collectiveResponse, fixture),
          apiFootballPlayers(playerResponse, fixture)
        );
        result.estatisticas_salvas += 1;
        result.api_football += 1;
      } catch (error) {
        result.erros.push(
          `${game.id}: ${error instanceof Error ? error.message : String(error)}`
        );
      }
    }

    return Response.json({
      ok: result.erros.length === 0,
      ...result,
      executado_em: new Date().toISOString(),
    });
  } catch (error) {
    result.erros.push(error instanceof Error ? error.message : String(error));
    return Response.json(
      {
        ok: false,
        ...result,
        executado_em: new Date().toISOString(),
      },
      { status: 500 }
    );
  }
}
