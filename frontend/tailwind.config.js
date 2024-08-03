module.exports = {
  purge: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
  theme: {
    extend: {
      colors: {
        awsOrange: "#FF9900",
        awsOrangeDark: "#CC7A00",
      },
      minHeight: {
        custom: "400px", // Custom min-height value
      },
      width: {
        custom: "500px", // Custom width value
      },
    },
  },
  variants: {
    extend: {},
  },
  plugins: [],
};
