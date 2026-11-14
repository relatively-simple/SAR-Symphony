declare module "plotly.js-basic-dist-min" {
  const Plotly: {
    newPlot: (el: HTMLElement, data: any[], layout?: any, config?: any) => Promise<void>;
    react: (el: HTMLElement, data: any[], layout?: any, config?: any) => Promise<void>;
    purge: (el: HTMLElement) => void;
  };
  export default Plotly;
}
