export type InsightRangePreset =
  | "TODAY"
  | "LAST_7_DAYS"
  | "LAST_30_DAYS"
  | "ALL_TIME"
  | "CUSTOM";

export interface DateRange {
  start: string;
  end: string;
  label: string;
}

export interface ComparisonDateRange {
  start: string;
  end: string;
  label: string;
}

function startOfLocalDay(date: Date): Date {
  const result = new Date(date);
  result.setHours(0, 0, 0, 0);
  return result;
}

function endOfLocalDay(date: Date): Date {
  const result = startOfLocalDay(date);
  result.setDate(result.getDate() + 1);
  return result;
}

function formatDate(date: Date): string {
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year:
      date.getFullYear() === new Date().getFullYear()
        ? undefined
        : "numeric",
  });
}

export function getCurrentLocalDateTime(): string {
  const now = new Date();

  return new Date(
    now.getTime() - now.getTimezoneOffset() * 60_000,
  )
    .toISOString()
    .slice(0, 16);
}

export function getLocalDayRange(date = new Date()): {
  start: string;
  end: string;
} {
  return {
    start: startOfLocalDay(date).toISOString(),
    end: endOfLocalDay(date).toISOString(),
  };
}

export function getInsightDateRange(
  preset: InsightRangePreset,
  birthDate: string,
  customStart?: string,
  customEnd?: string,
): DateRange {
  const now = new Date();
  const end = endOfLocalDay(now);

  if (preset === "TODAY") {
    return {
      start: startOfLocalDay(now).toISOString(),
      end: end.toISOString(),
      label: "Today",
    };
  }

  if (preset === "LAST_7_DAYS") {
    const start = startOfLocalDay(now);
    start.setDate(start.getDate() - 6);

    return {
      start: start.toISOString(),
      end: end.toISOString(),
      label: "Last 7 days",
    };
  }

  if (preset === "LAST_30_DAYS") {
    const start = startOfLocalDay(now);
    start.setDate(start.getDate() - 29);

    return {
      start: start.toISOString(),
      end: end.toISOString(),
      label: "Last 30 days",
    };
  }

  if (preset === "ALL_TIME") {
    return {
      start: startOfLocalDay(
        new Date(`${birthDate}T00:00:00`),
      ).toISOString(),
      end: end.toISOString(),
      label: "All-time insights",
    };
  }

  const selectedStart = customStart
    ? startOfLocalDay(new Date(`${customStart}T00:00:00`))
    : startOfLocalDay(now);

  const selectedEnd = customEnd
    ? endOfLocalDay(new Date(`${customEnd}T00:00:00`))
    : end;

  return {
    start: selectedStart.toISOString(),
    end: selectedEnd.toISOString(),
    label: `${formatDate(selectedStart)}–${formatDate(
      new Date(selectedEnd.getTime() - 1),
    )}`,
  };
}

export function getPreviousInsightDateRange(
  preset: InsightRangePreset,
  currentRange: DateRange,
): ComparisonDateRange | null {
  if (preset === "ALL_TIME") {
    return null;
  }

  const currentStart = new Date(currentRange.start);
  const currentEnd = new Date(currentRange.end);
  const duration = currentEnd.getTime() - currentStart.getTime();

  const previousEnd = new Date(currentStart);
  const previousStart = new Date(
    previousEnd.getTime() - duration,
  );

  let label = "Previous period";

  if (preset === "TODAY") {
    label = "Yesterday";
  } else if (preset === "LAST_7_DAYS") {
    label = "Previous 7 days";
  } else if (preset === "LAST_30_DAYS") {
    label = "Previous 30 days";
  }

  return {
    start: previousStart.toISOString(),
    end: previousEnd.toISOString(),
    label,
  };
}