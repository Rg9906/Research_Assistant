/**
 * Optional procedural ambience — generated live with the Web Audio API, no asset.
 *
 * The brief asks for hooks for deep-water ambience / sub-bass swell / soft pad /
 * shimmer, with no autoplay. Rather than ship an audio file, we synthesize it:
 * a sub sine, a filtered saw pad, and band-passed noise "shimmer", all under a
 * slow LFO. It only ever starts from a user gesture (the sound toggle), so it
 * never trips browser autoplay policy.
 */
export class AmbientSound {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private started = false;

  async enable(): Promise<void> {
    if (!this.ctx) {
      const AC = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.ctx = new AC();
    }
    const ctx = this.ctx;
    if (ctx.state === 'suspended') await ctx.resume();

    if (!this.started) {
      this.build(ctx);
      this.started = true;
    }
    if (this.master) {
      const now = ctx.currentTime;
      this.master.gain.cancelScheduledValues(now);
      this.master.gain.setValueAtTime(this.master.gain.value, now);
      this.master.gain.linearRampToValueAtTime(0.14, now + 2.5); // slow swell in
    }
  }

  disable(): void {
    if (!this.ctx || !this.master) return;
    const now = this.ctx.currentTime;
    this.master.gain.cancelScheduledValues(now);
    this.master.gain.setValueAtTime(this.master.gain.value, now);
    this.master.gain.linearRampToValueAtTime(0, now + 0.8);
  }

  private build(ctx: AudioContext): void {
    const master = ctx.createGain();
    master.gain.value = 0;
    master.connect(ctx.destination);
    this.master = master;

    // Sub sine — the "depth".
    const sub = ctx.createOscillator();
    sub.type = 'sine';
    sub.frequency.value = 55;
    const subGain = ctx.createGain();
    subGain.gain.value = 0.5;
    sub.connect(subGain).connect(master);

    // Detuned saw pad through a moving lowpass — the "synth pad".
    const padFilter = ctx.createBiquadFilter();
    padFilter.type = 'lowpass';
    padFilter.frequency.value = 380;
    padFilter.Q.value = 6;
    const padGain = ctx.createGain();
    padGain.gain.value = 0.16;
    padFilter.connect(padGain).connect(master);
    [110, 110.4, 164.8].forEach((f) => {
      const o = ctx.createOscillator();
      o.type = 'sawtooth';
      o.frequency.value = f;
      o.connect(padFilter);
      o.start();
    });

    // Band-passed noise — "water shimmer".
    const noiseBuf = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate);
    const data = noiseBuf.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
    const noise = ctx.createBufferSource();
    noise.buffer = noiseBuf;
    noise.loop = true;
    const bp = ctx.createBiquadFilter();
    bp.type = 'bandpass';
    bp.frequency.value = 2200;
    bp.Q.value = 0.8;
    const noiseGain = ctx.createGain();
    noiseGain.gain.value = 0.05;
    noise.connect(bp).connect(noiseGain).connect(master);

    // Slow LFO drifting the pad filter — keeps it breathing.
    const lfo = ctx.createOscillator();
    lfo.type = 'sine';
    lfo.frequency.value = 0.06;
    const lfoGain = ctx.createGain();
    lfoGain.gain.value = 220;
    lfo.connect(lfoGain).connect(padFilter.frequency);

    sub.start();
    noise.start();
    lfo.start();
  }
}
