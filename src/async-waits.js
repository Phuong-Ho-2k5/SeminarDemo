export const WAIT_MS = 1000;
export const TASK_COUNT = 3;

const wait = ms => scheduler.wait(ms);

export async function runSequential(waitFor = wait) {
  for (let task = 0; task < TASK_COUNT; task++) await waitFor(WAIT_MS);
}

export async function runParallel(waitFor = wait) {
  // Start all three independent waits BEFORE awaiting Promise.all.
  const tasks = Array.from({ length: TASK_COUNT }, () => waitFor(WAIT_MS));
  await Promise.all(tasks);
}
